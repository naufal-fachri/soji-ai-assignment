import argparse
from loguru import logger

from src.pipeline.llm_pipeline import ADRecognitionFullLLM
from src.pipeline.ocr_llm_pipeline import ADRecognitionOCR
from src.config import settings
from src.core.schemas import ADApplicabilityExtraction
from src.core.prompt import SYSTEM_PROMPT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="🛫 AD Recognition Pipeline — Extract and classify Airworthiness Directives",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "ocr"],
        default="ocr",
        help="Pipeline mode:\n  llm = Send images directly to Gemini\n  ocr = OCR first, then send text to Gemini (default)",
    )

    parser.add_argument(
        "--ad-files",
        type=str,
        nargs="+",
        required=True,
        help="Path(s) to AD PDF files\n  e.g. --ad-files ad1.pdf ad2.pdf ad3.pdf",
    )

    parser.add_argument(
        "--test-data",
        type=str,
        required=True,
        help="Path to test data CSV file",
    )

    parser.add_argument(
        "--save-dir",
        type=str,
        default="./results",
        help="Directory to save results (default: ./results)",
    )

    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temp directories after pipeline completes (for debugging)",
    )

    parser.add_argument(
        "--no-ocr-viz",
        action="store_true",
        help="Skip saving OCR bbox visualizations (ocr mode only)",
    )

    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device for inference:\n  cpu = CPU inference\n  gpu:0 = GPU 0 (default from settings)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("🔰" + "=" * 58)
    logger.info(f"🛫 AD Recognition Pipeline — Mode: {args.mode.upper()}")
    logger.info(f"📋 AD files: {len(args.ad_files)} file(s)")
    logger.info(f"📊 Test data: {args.test_data}")
    logger.info(f"💾 Save dir: {args.save_dir}")
    logger.info("🔰" + "=" * 58)

    if args.mode == "llm":
        pipeline = ADRecognitionFullLLM(
            dpi=settings.DPI,
            llm_model=settings.GEMINI_MODEL,
            llm_system_prompt=SYSTEM_PROMPT,
            llm_temperature=settings.GEMINI_TEMPERATURE,
            llm_output_schema=ADApplicabilityExtraction,
        )

    elif args.mode == "ocr":
        ocr_device = args.device if args.device else settings.OCR_DEVICE
        pipeline = ADRecognitionOCR(
            dpi=settings.DPI,
            llm_model=settings.GEMINI_MODEL,
            llm_system_prompt=SYSTEM_PROMPT,
            llm_temperature=settings.GEMINI_TEMPERATURE,
            llm_output_schema=ADApplicabilityExtraction,
            ocr_device=ocr_device,
            ocr_precision=settings.OCR_PRECISION,
            ocr_det_model=settings.OCR_DET_MODEL,
            ocr_rec_model=settings.OCR_REC_MODEL,
            y_threshold=settings.OCR_Y_THRESHOLD,
            save_ocr_viz=not args.no_ocr_viz,
            cpu_threads=settings.OCR_CPU_THREADS,
        )

    result_path = pipeline.run_analysis(
        test_data_path=args.test_data,
        ad_file_paths=args.ad_files,
        save_dir=args.save_dir,
        cleanup=not args.no_cleanup,
    )

    logger.info(f"📄 Results available at: {result_path}")


if __name__ == "__main__":
    main()