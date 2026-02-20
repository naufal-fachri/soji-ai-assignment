import os
import json
import shutil
import pandas as pd
from datetime import datetime
from uuid import uuid4
from typing import Optional
from loguru import logger
from pydantic import BaseModel
from google import genai
from google.genai import types
from pdf2image import convert_from_bytes
from src.core.utils import compare_to_ad
from src.config import settings


class ADRecognitionFullLLM:
    def __init__(
        self,
        dpi: int,
        llm_model: str,
        llm_system_prompt: str,
        llm_temperature: float,
        llm_output_schema: type[BaseModel],
        temp_dir: Optional[str] = None,
    ):
        self.dpi = dpi
        self.llm_client = genai.Client(
            api_key=settings.GOOGLE_API_KEY
        )
        self.llm_model = llm_model
        self.llm_system_prompt = llm_system_prompt
        self.llm_temperature = llm_temperature
        self.llm_output_schema = llm_output_schema

        if not temp_dir:
            current_dir = os.getcwd()
            self.temp_dir = os.path.join(current_dir, "tmp/ad_recognition")

        else:
            self.temp_dir = temp_dir
            
        os.makedirs(self.temp_dir, exist_ok=True)
        self._run_dirs: list[str] = []  # track created run dirs for cleanup

    # ------------------------------------------------------------------ #
    #  Helper: Derive AD label from filename
    # ------------------------------------------------------------------ #
    @staticmethod
    def _label_from_path(pdf_path: str) -> str:
        return os.path.splitext(os.path.basename(pdf_path))[0]

    # ------------------------------------------------------------------ #
    #  Cleanup
    # ------------------------------------------------------------------ #
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

        # Remove parent temp dir if empty
        try:
            if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)
                logger.debug(f"   🗑️  Removed empty temp dir: {self.temp_dir}")
        except Exception:
            pass

        logger.info("✅ Cleanup complete")

    # ------------------------------------------------------------------ #
    #  Step 1: PDF -> Images
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    #  Step 2: Prepare LLM messages
    # ------------------------------------------------------------------ #
    def _prepare_messages(self, img_paths: list[str]) -> list:
        logger.info(f"📦 Preparing {len(img_paths)} images for LLM...")
        messages = ["Now, extract the following images!"]
        for img_path in img_paths:
            logger.debug(f"   🔗 Encoding: {os.path.basename(img_path)}")
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            messages.append(
                types.Part.from_bytes(
                    data=img_bytes,
                    mime_type="image/png",
                )
            )
        logger.info("✅ All images encoded and ready")
        return messages

    # ------------------------------------------------------------------ #
    #  Step 3: Call Gemini for structured extraction
    # ------------------------------------------------------------------ #
    def _extract_with_llm(self, messages: list) -> dict:
        logger.info(f"🤖 Calling LLM model: {self.llm_model}")

        config = types.GenerateContentConfig(
            system_instruction=self.llm_system_prompt,
            temperature=self.llm_temperature,
            response_mime_type="application/json",
            response_json_schema=self.llm_output_schema.model_json_schema(),
        )

        response = self.llm_client.models.generate_content(
            model=self.llm_model,
            config=config,
            contents=messages,
        )

        parsed = self.llm_output_schema.model_validate_json(response.text)
        logger.info("🎯 LLM extraction completed successfully")
        return parsed.model_dump()

    # ------------------------------------------------------------------ #
    #  Step 4: Save extraction results
    # ------------------------------------------------------------------ #
    def _save_extraction(self, data: dict, run_dir: str, label: str) -> str:
        out_path = os.path.join(run_dir, f"{label}_extraction.json")
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved extraction: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Step 5: Extract a single AD PDF
    # ------------------------------------------------------------------ #
    def extract_ad(self, pdf_path: str, label: Optional[str] = None) -> dict:
        if label is None:
            label = self._label_from_path(pdf_path)

        run_id = uuid4().hex
        run_dir = os.path.join(self.temp_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        self._run_dirs.append(run_dir)
        logger.info(f"🚀 [{label}] Starting extraction — run_id={run_id}")

        img_paths = self._pdf_to_images(pdf_path, run_dir)
        messages = self._prepare_messages(img_paths)
        extraction = self._extract_with_llm(messages)
        self._save_extraction(extraction, run_dir, label)

        logger.info(f"✅ [{label}] Extraction complete!")
        return extraction

    # ------------------------------------------------------------------ #
    #  Step 6: Full pipeline
    # ------------------------------------------------------------------ #
    def run_analysis(
        self,
        test_data_path: str,
        ad_file_paths: list[str],
        save_dir: str,
        cleanup: bool = True,
    ) -> str:
        """
        Run the complete AD recognition and comparison pipeline.

        Args:
            test_data_path: Path to test CSV file.
            ad_file_paths: List of AD PDF file paths to extract and compare.
            save_dir: Directory to save final results.
            cleanup: Whether to delete temp directories after saving results.

        Returns:
            Path to the saved results CSV.
        """
        logger.info("🔰" + "=" * 58)
        logger.info(f"🛫 Starting AD Recognition Pipeline — {len(ad_file_paths)} AD(s)")
        logger.info("🔰" + "=" * 58)

        try:
            # --- Extract all AD PDFs ---
            ad_extractions: dict[str, dict] = {}
            for i, pdf_path in enumerate(ad_file_paths, 1):
                label = self._label_from_path(pdf_path)
                logger.info(f"📋 [{i}/{len(ad_file_paths)}] Processing: {label}")
                extraction = self.extract_ad(pdf_path, label=label)
                ad_extractions[label] = extraction

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
            run_timestamp = datetime.now().strftime("%y%m%d")
            run_id = uuid4().hex[:8]
            run_output_dir = os.path.join(save_dir, f"{run_id}_{run_timestamp}")
            os.makedirs(run_output_dir, exist_ok=True)
            logger.info(f"📁 Run output directory: {run_output_dir}")

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