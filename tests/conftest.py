from pathlib import Path

import pymupdf as fitz
import pytest


@pytest.fixture
def synthetic_drawing(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic-engineering-drawing.pdf"
    document = fitz.open()
    page = document.new_page(width=792, height=612)
    text = """RELEASED 17/Mar/2026 10:30:00 GMT
NOTES:
1. REMOVE ALL BURRS FROM FINISHED EDGES.
2. PART MUST CONFORM TO SPECIFICATION ASME Y14.5-2018 AND ISO 2768-1.
QTY ITEM PART NO. DESCRIPTION
2 10 CMP-1001 RETAINER CLIP
SUPPLIER: ACME FABRICATION
SUPPLIER P/N: SF-88
THIS DRAWING HAS BEEN IDENTIFIED AS A CRITICAL ITEM.
SUPPLIER DRAWING
DRAWN BY J_SMITH
MODELED BY A_JONES
DATE 03/14/2026
PART NAME ACTUATOR BRACKET SIZE B DWG NO ZX-42017 REV D
ECN-2041 UPDATED MOUNTING SLOT 03/15/2026 J_SMITH R_APPROVER
WEIGHT KILOGRAMS 2.45 SCALE: 1:2 UNITS: mm SHEET 1 OF 2
"""
    page.insert_textbox(fitz.Rect(36, 36, 756, 570), text, fontsize=10, fontname="courier")
    document.save(path)
    document.close()
    return path


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "blank.pdf"
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()
    return path
