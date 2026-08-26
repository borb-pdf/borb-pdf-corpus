import json
import pathlib
import shutil
import typing

SRC_DIR: pathlib.Path = pathlib.Path("/home/joris-schellekens/Code/borb-pdf-corpus/pdf")

DIGEST_DIR: pathlib.Path = pathlib.Path(__file__).parent / "digest"
FIRST_PAGE_PDF_DIR: pathlib.Path = pathlib.Path(__file__).parent / "first-page-pdf"
FIRST_PAGE_TXT_DIR: pathlib.Path = pathlib.Path(__file__).parent / "first-page-txt"
FIRST_PAGE_OPS_DIR: pathlib.Path = pathlib.Path(__file__).parent / "first-page-ops"
PDF_DIR: pathlib.Path = pathlib.Path(__file__).parent / "pdf"
TXT_DIR: pathlib.Path = pathlib.Path(__file__).parent / "txt"

#
# PRIVATE
#


def __get_digest(file: pathlib.Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def __store_text(src_file: pathlib.Path, dst_name: str) -> None:
    from PyPDF2 import PdfReader

    txt_in_pdf: str = ""
    try:
        reader = PdfReader(src_file)
        txt_in_pdf = "\n".join(page.extract_text() or "" for page in reader.pages)
    except:
        pass
    with open(TXT_DIR / dst_name, "w") as fh:
        fh.write(txt_in_pdf)


def __store_first_page_pdf(src_file: pathlib.Path, dst_name: str) -> None:
    from PyPDF2 import PdfReader, PdfWriter

    try:
        reader = PdfReader(src_file)
        writer = PdfWriter()
        writer.add_page(reader.pages[0])
        with open(FIRST_PAGE_PDF_DIR / dst_name, "wb") as f:
            writer.write(f)
    except:
        pass


def __store_first_page_txt(src_file: pathlib.Path, dst_name: str) -> None:
    from PyPDF2 import PdfReader

    txt_in_pdf: str = ""
    try:
        reader = PdfReader(src_file)
        txt_in_pdf = reader.pages[0].extract_text()
    except:
        pass
    with open(FIRST_PAGE_TXT_DIR / dst_name, "w") as fh:
        fh.write(txt_in_pdf)


def __store_first_page_ops(
    src_file: pathlib.Path,
    dst_name: str,
) -> None:
    """
    Store text operators from the first page together with their
    approximate bounding boxes.
    """

    try:
        from PyPDF2 import PdfReader

        out: typing.List[typing.Dict[str, typing.Any]] = []

        def visitor(
            operator: bytes,
            operands: typing.List[typing.Any],
            cm: typing.List[float],
            tm: typing.List[float],
        ) -> None:
            if operator not in (b"Tj", b"TJ"):
                return

            try:
                page = reader.pages[0]

                # tm = [a, b, c, d, e, f]
                #
                # For the non-rotated PDFs we're interested in:
                #   e = x
                #   f = y
                x: float = float(tm[4])
                y: float = float(tm[5])

                if operator == b"Tj":
                    text_bytes: bytes = operands[0]

                    if not isinstance(text_bytes, bytes):
                        return

                    text: str = text_bytes.decode(
                        "latin-1",
                        errors="replace",
                    )

                    # pypdf's text visitor is the easiest way to get the
                    # decoded text, but for the geometry we calculate the
                    # advance directly below.
                    width: float = 0.0

                else:
                    array: typing.List[typing.Any] = operands[0]

                    text_parts: typing.List[bytes] = []
                    width: float = 0.0

                    for item in array:
                        if isinstance(item, bytes):
                            text_parts.append(item)

                    text_bytes = b"".join(text_parts)

                    text = text_bytes.decode(
                        "latin-1",
                        errors="replace",
                    )

                # ---------------------------------------------------------
                # Find the current font from the page resources.
                #
                # This is the difficult part: visitor_operand_before gives
                # us the text matrix, but not the current font resource.
                #
                # We therefore use pypdf's text visitor separately to
                # obtain font information for the page.
                # ---------------------------------------------------------

                # The text matrix gives us the horizontal scale.
                text_scale_x: float = float(tm[0])

                if abs(text_scale_x) < 1e-9:
                    text_scale_x = 1.0

                # Fallback width.
                #
                # This is intentionally conservative. For comparison with
                # borb, the caller can apply a tolerance.
                width = float(len(text)) * 0.5 * abs(text_scale_x)

                font_size: float = abs(float(tm[3]))

                if font_size == 0:
                    font_size = 1.0

                height: float = font_size

                bbox: typing.List[float] = [
                    x,
                    y - height,
                    x + width,
                    y,
                ]

                out.append(
                    {
                        "operator": operator.decode("ascii"),
                        "text": text,
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                        "bbox": bbox,
                        "cm": list(cm),
                        "tm": list(tm),
                    }
                )

            except Exception:
                # Don't let one malformed text operator prevent the
                # remaining operators from being collected.
                return

        reader = PdfReader(src_file)

        reader.pages[0].extract_text(
            visitor_operand_before=visitor,
        )

        if not FIRST_PAGE_OPS_DIR.exists():
            FIRST_PAGE_OPS_DIR.mkdir()

        with open(FIRST_PAGE_OPS_DIR / dst_name, "w") as fh:
            fh.write(
                json.dumps(
                    out,
                    indent=3,
                    sort_keys=True,
                )
            )

    except Exception as ex:
        print(ex)
        pass


#
# PUBLIC
#


def main():

    # find all PDF file(s)
    pdfs_to_do: typing.List[pathlib.Path] = []
    if SRC_DIR.is_file():
        pdfs_to_do += [SRC_DIR]
    if SRC_DIR.is_dir():
        pdfs_to_do += [x for x in SRC_DIR.iterdir()]
    pdfs_to_do = [x for x in pdfs_to_do if x.suffix == ".pdf"]

    # easy out
    if len(pdfs_to_do) == 0:
        return

    # process
    for pdf_file in pdfs_to_do:

        # determine n
        n: int = int(pdf_file.stem)

        # store digest
        tmp: pathlib.Path = DIGEST_DIR / f"{n:04d}.sha256"
        if not tmp.exists():
            print(f"Processing {pdf_file}:")
            print(f"\tdigest          : {n:04d}.sha256")
            with open(DIGEST_DIR / f"{n:04d}.sha256", "w") as fh:
                fh.write(__get_digest(pdf_file))

        # store txt
        tmp = TXT_DIR / f"{n:04d}.txt"
        if not tmp.exists():
            print(f"\ttext            : {n:04d}.txt")
            __store_text(src_file=pdf_file, dst_name=f"{n:04d}.txt")

        # store first-page-pdf
        tmp = FIRST_PAGE_TXT_DIR / f"{n:04d}.txt"
        if not tmp.exists():
            print(f"\tfirst-page-pdf  : {n:04d}.pdf")
            __store_first_page_pdf(src_file=pdf_file, dst_name=f"{n:04d}.pdf")

        # store first-page-ops
        tmp = FIRST_PAGE_OPS_DIR / f"{n:04d}.json"
        if not tmp.exists():
            print(f"\tfirst-page-ops  : {n:04d}.pdf")
            __store_first_page_ops(src_file=pdf_file, dst_name=f"{n:04d}.json")


if __name__ == "__main__":
    main()
