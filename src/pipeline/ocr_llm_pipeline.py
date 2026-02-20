import os
import json
import shutil
import numpy as np
import pandas as pd

from datetime import datetime
from uuid import uuid4
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from loguru import logger
from pydantic import BaseModel
from google import genai
from google.genai import types
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR
from src.core.utils import compare_to_ad
from src.config import settings

class ADRecognitionOCR:
    def __init__(
        self,
        dpi: int,
        llm_model: str,
        llm_system_prompt: str,
        llm_temperature: float,
        llm_output_schema: type[BaseModel],
        ocr_device: str = "gpu:0",
        ocr_precision: str = "fp16",
        ocr_det_model: str = "PP-OCRv5_mobile_det",
        ocr_rec_model: str = "PP-OCRv5_mobile_rec",
        y_threshold: float = 15.0,
        save_ocr_viz: bool = True,
        cpu_threads: int = 8,
        temp_dir: Optional[str] = None,
    ):
        self.dpi = dpi
        self.y_threshold = y_threshold
        self.save_ocr_viz = save_ocr_viz

        # --- LLM ---
        self.llm_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.llm_model = llm_model
        self.llm_system_prompt = llm_system_prompt
        self.llm_temperature = llm_temperature
        self.llm_output_schema = llm_output_schema

        # --- OCR Engine ---
        is_cpu = ocr_device.lower() == "cpu"

        if is_cpu:
            logger.info(f"🔧 Initializing PaddleOCR engine on CPU with {cpu_threads} threads...")
            _precision = "fp32"
            _enable_mkldnn = False
        else:
            logger.info(f"🔧 Initializing PaddleOCR engine on {ocr_device}...")
            _precision = ocr_precision
            _enable_mkldnn = True

        self.ocr_engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=ocr_device,
            precision=_precision,
            enable_mkldnn=_enable_mkldnn,
            text_detection_model_name=ocr_det_model,
            text_recognition_model_name=ocr_rec_model,
            cpu_threads=cpu_threads if is_cpu else None,
        )

        if is_cpu:
            logger.info(f"✅ PaddleOCR engine ready (CPU mode — {cpu_threads} threads, mkldnn=off, fp32)")
        else:
            logger.info(f"✅ PaddleOCR engine ready ({ocr_device}, {ocr_precision})")

        # --- Temp dir ---
        if not temp_dir:
            self.temp_dir = os.path.join(os.getcwd(), "tmp/ad_recognition_ocr")
        else:
            self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        self._run_dirs: list[str] = []

    # ================================================================== #
    #  Helpers
    # ================================================================== #
    @staticmethod
    def _label_from_path(pdf_path: str) -> str:
        return os.path.splitext(os.path.basename(pdf_path))[0]

    def _cleanup_temp(self):
        """Remove all temporary run directories created during this session."""
        if not self._run_dirs:
            return

        logger.info(f"🧹 Cleaning up {len(self._run_dirs)} temp directories...")
        for run_dir in self._run_dirs:
            try:
                shutil.rmtree(run_dir)
                logger.debug(f"   🗑️  Removed: {run_dir}")
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to remove {run_dir}: {e}")
        self._run_dirs.clear()

        try:
            if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)
                logger.debug(f"   🗑️  Removed empty temp dir: {self.temp_dir}")
        except Exception:
            pass

        logger.info("✅ Cleanup complete")

    # ================================================================== #
    #  Step 1: PDF -> Images
    # ================================================================== #
    def _pdf_to_images(self, pdf_path: str, run_dir: str) -> list[str]:
        logger.info(f"📄 Converting PDF to images: {pdf_path} (dpi={self.dpi})")
        imgs_dir = os.path.join(run_dir, "pages")
        os.makedirs(imgs_dir, exist_ok=True)

        with open(pdf_path, "rb") as f:
            img_paths = convert_from_bytes(
                f.read(),
                output_folder=imgs_dir,
                fmt="png",
                paths_only=True,
                dpi=self.dpi,
            )
        logger.info(f"🖼️  Generated {len(img_paths)} page images")
        return img_paths

    # ================================================================== #
    #  Step 2: OCR
    # ================================================================== #
    def _run_ocr(self, img_paths: list[str]) -> list[dict]:
        logger.info(f"🔍 Running OCR on {len(img_paths)} pages...")
        ocr_results = list(self.ocr_engine.predict(img_paths))
        logger.info(f"✅ OCR complete — {len(ocr_results)} pages processed")
        return ocr_results

    # ================================================================== #
    #  Step 3: OCR Postprocessing (sort + full text)
    # ================================================================== #
    @staticmethod
    def _sort_ocr_reading_order(
        texts: List[str],
        boxes: List[np.ndarray],
        y_threshold: float = 15.0,
    ) -> tuple[List[str], List[np.ndarray]]:
        """Sort OCR results in natural reading order (top-to-bottom, left-to-right)."""
        if not texts:
            return texts, boxes

        coords = []
        for i, box in enumerate(boxes):
            box = np.array(box)
            if box.shape == (4,):
                x_left = box[0]
                y_center = (box[1] + box[3]) / 2
            elif box.shape == (4, 2):
                x_left = box[:, 0].min()
                y_center = box[:, 1].mean()
            else:
                raise ValueError(f"Unexpected box shape: {box.shape}")
            coords.append((i, x_left, y_center))

        coords.sort(key=lambda c: c[2])

        lines = []
        current_line = [coords[0]]
        for item in coords[1:]:
            if abs(item[2] - current_line[0][2]) <= y_threshold:
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]
        lines.append(current_line)

        sorted_indices = []
        for line in lines:
            line.sort(key=lambda c: c[1])
            sorted_indices.extend([item[0] for item in line])

        sorted_texts = [texts[i] for i in sorted_indices]
        sorted_boxes = [boxes[i] for i in sorted_indices]
        return sorted_texts, sorted_boxes

    def _get_full_text(self, ocr_results: List[Dict[str, Any]]) -> str:
        """Convert OCR results to full text in reading order with page headers."""
        all_pages_text = []
        total_pages = len(ocr_results)

        for page_idx, page in enumerate(ocr_results):
            texts = page.get("rec_texts", [])
            boxes = page.get("rec_boxes", [])

            if not texts:
                continue

            sorted_texts, sorted_boxes = self._sort_ocr_reading_order(
                texts, boxes, self.y_threshold
            )

            coords = []
            for i, box in enumerate(sorted_boxes):
                box = np.array(box)
                if box.shape == (4,):
                    y_center = (box[1] + box[3]) / 2
                else:
                    y_center = box[:, 1].mean()
                coords.append((i, y_center))

            lines_text = []
            current_line_texts = [sorted_texts[0]]
            current_y = coords[0][1]

            for idx in range(1, len(coords)):
                if abs(coords[idx][1] - current_y) <= self.y_threshold:
                    current_line_texts.append(sorted_texts[idx])
                else:
                    line = " ".join(t for t in current_line_texts if t.strip())
                    if line.strip():
                        lines_text.append(line)
                    current_line_texts = [sorted_texts[idx]]
                    current_y = coords[idx][1]

            line = " ".join(t for t in current_line_texts if t.strip())
            if line.strip():
                lines_text.append(line)

            page_num = page_idx + 1
            header = f"\n{'='*60}\n  PAGE {page_num} / {total_pages}\n{'='*60}\n"
            all_pages_text.append(header + "\n".join(lines_text))

        return "\n".join(all_pages_text)

    # ================================================================== #
    #  Step 4: Draw OCR bbox visualizations
    # ================================================================== #
    @staticmethod
    def _draw_ocr_bboxes(
        image_path: str,
        ocr_result: dict,
        output_path: str,
        use_polys: bool = True,
        box_color: str = "red",
        text_color: str = "blue",
        show_text: bool = False,
        font_size: int = 14,
    ) -> None:
        """Draw OCR bounding boxes on the original image and save."""
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        texts = ocr_result.get("rec_texts", [])
        polys = ocr_result.get("rec_polys" if use_polys else "rec_boxes", [])

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
            )
        except Exception:
            font = ImageFont.load_default()

        for i, poly in enumerate(polys):
            poly = np.array(poly)

            if poly.shape == (4,):
                x_min, y_min, x_max, y_max = poly
                draw.rectangle([x_min, y_min, x_max, y_max], outline=box_color, width=2)
                text_pos = (x_min, y_min - font_size - 2)
            elif poly.shape == (4, 2):
                points = [tuple(p) for p in poly.astype(int)]
                points.append(points[0])
                draw.line(points, fill=box_color, width=2)
                text_pos = (int(poly[:, 0].min()), int(poly[:, 1].min()) - font_size - 2)
            else:
                continue

            if show_text and i < len(texts) and texts[i].strip():
                draw.text(text_pos, texts[i], fill=text_color, font=font)

        img.save(output_path)

    def _save_ocr_visualizations(
        self,
        img_paths: list[str],
        ocr_results: list[dict],
        save_dir: str,
        label: str,
    ) -> list[str]:
        """Draw and save bbox visualizations for all pages."""
        viz_dir = os.path.join(save_dir, f"{label}_ocr_viz")
        os.makedirs(viz_dir, exist_ok=True)
        viz_paths = []

        logger.info(f"🎨 Drawing OCR visualizations for {len(img_paths)} pages...")
        for i, (img_path, ocr_result) in enumerate(zip(img_paths, ocr_results)):
            viz_path = os.path.join(viz_dir, f"page_{i+1}_ocr_viz.png")
            self._draw_ocr_bboxes(
                image_path=img_path,
                ocr_result=ocr_result,
                output_path=viz_path,
            )
            viz_paths.append(viz_path)
            logger.debug(f"   🖍️  Saved viz: page {i+1}")

        logger.info(f"✅ All OCR visualizations saved to: {viz_dir}")
        return viz_paths

    # ================================================================== #
    #  Step 5: LLM extraction (text-only input)
    # ================================================================== #
    def _extract_with_llm(self, full_text: str) -> dict:
        logger.info(f"🤖 Calling LLM model: {self.llm_model} (text-only mode)")

        config = types.GenerateContentConfig(
            system_instruction=self.llm_system_prompt,
            temperature=self.llm_temperature,
            response_mime_type="application/json",
            response_json_schema=self.llm_output_schema.model_json_schema(),
        )

        response = self.llm_client.models.generate_content(
            model=self.llm_model,
            config=config,
            contents=f"Now extract the following OCR'd text:\n\n{full_text}",
        )

        parsed = self.llm_output_schema.model_validate_json(response.text)
        logger.info("🎯 LLM extraction completed successfully")
        return parsed.model_dump()

    # ================================================================== #
    #  Step 6: Save extraction results
    # ================================================================== #
    def _save_extraction(self, data: dict, run_dir: str, label: str) -> str:
        out_path = os.path.join(run_dir, f"{label}_extraction.json")
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved extraction: {out_path}")
        return out_path

    # ================================================================== #
    #  Step 7: Extract a single AD PDF (full OCR pipeline)
    # ================================================================== #
    def extract_ad(
        self, pdf_path: str, label: Optional[str] = None
    ) -> tuple[dict, list[str], list[dict]]:
        """
        Full OCR extraction pipeline for a single AD PDF.

        Returns:
            (extraction_dict, img_paths, ocr_results)
        """
        if label is None:
            label = self._label_from_path(pdf_path)

        run_id = uuid4().hex
        run_dir = os.path.join(self.temp_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        self._run_dirs.append(run_dir)
        logger.info(f"🚀 [{label}] Starting OCR extraction — run_id={run_id}")

        # PDF -> Images
        img_paths = self._pdf_to_images(pdf_path, run_dir)

        # Images -> OCR
        ocr_results = self._run_ocr(img_paths)

        # OCR -> Sorted full text
        full_text = self._get_full_text(ocr_results)
        logger.info(f"📝 Full text extracted: {len(full_text)} characters")

        # Save raw OCR text for debugging
        text_path = os.path.join(run_dir, f"{label}_ocr_text.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        logger.debug(f"   📄 Raw OCR text saved: {text_path}")

        # Text -> LLM structured extraction
        extraction = self._extract_with_llm(full_text)
        self._save_extraction(extraction, run_dir, label)

        logger.info(f"✅ [{label}] OCR extraction complete!")
        return extraction, img_paths, ocr_results

    # ================================================================== #
    #  Step 8: Full pipeline
    # ================================================================== #
    def run_analysis(
        self,
        test_data_path: str,
        ad_file_paths: list[str],
        save_dir: str,
        cleanup: bool = True,
    ) -> str:
        logger.info("🔰" + "=" * 58)
        logger.info(f"🛫 Starting AD Recognition Pipeline (OCR) — {len(ad_file_paths)} AD(s)")
        logger.info("🔰" + "=" * 58)

        try:
            # --- Extract all AD PDFs via OCR ---
            ad_extractions: dict[str, dict] = {}
            ad_ocr_data: dict[str, tuple[list[str], list[dict]]] = {}

            for i, pdf_path in enumerate(ad_file_paths, 1):
                label = self._label_from_path(pdf_path)
                logger.info(f"📋 [{i}/{len(ad_file_paths)}] Processing: {label}")
                extraction, img_paths, ocr_results = self.extract_ad(pdf_path, label=label)
                ad_extractions[label] = extraction
                ad_ocr_data[label] = (img_paths, ocr_results)

            # --- Save OCR visualizations to save_dir ---

            run_timestamp = datetime.now().strftime("%y%m%d")
            run_id = uuid4().hex[:8]
            run_output_dir = os.path.join(save_dir, f"{run_id}_{run_timestamp}")
            os.makedirs(run_output_dir, exist_ok=True)
            logger.info(f"📁 Run output directory: {run_output_dir}")

            # --- Save OCR visualizations ---
            if self.save_ocr_viz:
                for label, (img_paths, ocr_results) in ad_ocr_data.items():
                    self._save_ocr_visualizations(
                        img_paths, ocr_results, run_output_dir, label
                    )

            # --- Load test data ---
            logger.info(f"📊 Loading test data: {test_data_path}")
            test_data = pd.read_csv(test_data_path, sep=",")
            logger.info(f"📐 Test data shape: {test_data.shape}")

            # --- Compare ---
            logger.info(f"⚙️  Running AD comparison against {len(ad_extractions)} AD(s)...")
            result_df = compare_to_ad(test_data, ad_file_dict=ad_extractions)
            logger.info(f"🏁 Comparison done — {len(result_df)} rows classified")

            # --- Present results ---
            print("========== RESULT ==========")
            print(result_df.to_markdown(index=False))
            print("============================")

            # --- Save results ---
            result_path = os.path.join(run_output_dir, "ad_classification_results.csv")
            result_df.to_csv(result_path, index=False)
            logger.info(f"💾 Results saved: {result_path}")

            extractions_path = os.path.join(run_output_dir, "ad_extractions.json")
            with open(extractions_path, "w") as f:
                json.dump(ad_extractions, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Extractions saved: {extractions_path}")

        finally:
            if cleanup:
                self._cleanup_temp()

        logger.info("🔰" + "=" * 58)
        logger.info("🎉 Pipeline complete!")
        logger.info("🔰" + "=" * 58)

        return result_path