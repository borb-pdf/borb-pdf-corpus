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


def __store_first_page_ops(src_file: pathlib.Path, dst_name: str):

    try:
        # define the output variable
        out: typing.List[typing.Dict[str, typing.Any]] = []

        # define inner function to pass to visitor
        def visitor(
            operator: bytes,
            operands: list,
            cm: list[float],
            tm: list[float],
        ) -> None:
            if operator not in (b"Tj", b"TJ"):
                return

            text = (
                operands[0]
                if operator == b"Tj"
                else b"".join(item for item in operands[0] if isinstance(item, bytes))
            )

            # tm = [a, b, c, d, e, f]
            # e, f are the current text position.
            x = tm[4]
            y = tm[5]

            try:
                out.append(
                    {
                        "operator": operator.decode(),
                        "text": text.decode(),
                        "x": x,
                        "y": y,
                        "cm": cm,
                        "tm": tm,
                    }
                )
            except:
                pass

        # read the file
        from PyPDF2 import PdfReader

        reader = PdfReader(src_file)

        # process first page with the visitor
        reader.pages[0].extract_text(
            visitor_operand_before=visitor,
        )

        # IF the FIRST_PAGE_OPS_DIR does not exist yet
        # THEN create it
        if not FIRST_PAGE_OPS_DIR.exists():
            FIRST_PAGE_OPS_DIR.mkdir()

        # store
        with open(FIRST_PAGE_OPS_DIR / dst_name, "w") as fh:
            fh.write(json.dumps(out, indent=3, sort_keys=True))
    except:
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

        # store first-page-txt
        tmp = FIRST_PAGE_OPS_DIR / f"{n:04d}.json"
        if not tmp.exists():
            print(f"\tfirst-page-ops  : {n:04d}.pdf")
            __store_first_page_ops(src_file=pdf_file, dst_name=f"{n:04d}.json")


if __name__ == "__main__":
    main()
