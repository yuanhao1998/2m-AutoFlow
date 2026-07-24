"""docTR OCR 引擎封装：用于结构化文本（数字、英文、符号）的高精度识别。

内置预训练模型 vocab 不含韩文，因此仅用于 allowlist 指定的字段
（如 IP 地址、主机名），韩文文本仍走 EasyOCR。
"""

from __future__ import annotations

import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_predictor = None


def _get_predictor():
    """懒加载 docTR OCR 预测器（内置预训练模型，支持数字+英文+符号）。"""
    global _predictor
    if _predictor is None:
        logger.info("正在加载 docTR 模型...")
        from doctr.models import ocr_predictor
        _predictor = ocr_predictor(
            det_arch="db_mobilenet_v3_large",
            reco_arch="crnn_mobilenet_v3_small",
            pretrained=True,
        )
        logger.info("docTR 模型加载完成")
    return _predictor


def readtext(image: np.ndarray, *, detail: int = 0,
             allowlist: str | None = None) -> list:
    """识别图像中的文字（仅限内置 vocab 支持的字符：数字、英文、符号）。

    Args:
        image: BGR numpy 数组。
        detail: 0 返回纯文本列表，1 返回 [(bbox, text, confidence), ...]。
        allowlist: 字符白名单，对结果做后处理过滤。

    Returns:
        detail=0: ["text1", "text2", ...]
        detail=1: [([[x1,y1],...], "text", confidence), ...]
    """
    predictor = _get_predictor()

    if image.ndim == 3 and image.shape[2] == 3:
        pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    else:
        pil = Image.fromarray(image)

    h, w = pil.height, pil.width

    # 小文本放大提升识别率
    if h < 30:
        pil = pil.resize((w * 3, h * 3), Image.LANCZOS)
        h, w = pil.height, pil.width

    buf = BytesIO()
    pil.save(buf, format="PNG")
    buf.seek(0)

    from doctr.io import DocumentFile
    doc = DocumentFile.from_images(buf.read())
    result = predictor(doc)

    outputs: list = []

    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    text = word.value or ""
                    conf = float(word.confidence)

                    if allowlist:
                        text = "".join(c for c in text if c in allowlist)
                    if not text:
                        continue

                    if detail == 0:
                        outputs.append(text)
                    else:
                        (x1, y1), (x2, y2) = word.geometry
                        bbox = [
                            [x1 * w, y1 * h], [x2 * w, y1 * h],
                            [x2 * w, y2 * h], [x1 * w, y2 * h],
                        ]
                        outputs.append((bbox, text, conf))

    return outputs
