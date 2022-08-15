import contextlib
import os
import textwrap

import PIL.Image
import pyheif

__all__ = [
    'load_heif',
    'images_to_pdf',
    'adjust_widths',
    'has_extension',
]


def has_extension(filename, exts):
    """check if filename has any one of the file extension in exts
    (case-insensitive)
    """
    filename = filename.lower()
    return any(filename.endswith(ext) for ext in exts)


def load_heif(file):
    """heif file -> Image object"""
    # example stolen from https://pypi.org/project/pyheif/
    heif_file = pyheif.read(file)
    return PIL.Image.frombytes(
        heif_file.mode,
        heif_file.size,
        heif_file.data,
        'raw',
        heif_file.mode,
        heif_file.stride)


def images_to_pdf(files, outfile, filters=None, **kwargs):
    """list of images -> a new PDF created at 'outfile'

    an optional list of filters is called when all images are loaded as
    Image objects, with filters coming earlier in the list called first.
    the filters each take a list of Image objects and returns a list of
    processed Image objects.

    extra keyword arguments are passed onto the PDF writer:
    https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#pdf
    """
    if not files:
        raise ValueError('empty image file list')
    for key in 'append_images', 'save_all':
        if key in kwargs:
            raise TypeError(f"cannot supply the {keys!r} keyword argument "
                            f"as it will be overridden")
    with contextlib.ExitStack() as stack:
        images = []
        for file in files:
            if has_extension(file, ['.heic', '.heif']):
                im = load_heif(file)
            else:
                im = stack.enter_context(PIL.Image.open(file))
            images.append(im)
        if filters is not None:
            for callback in filters:
                images = callback(images)
        images[0].save(outfile, 'PDF', save_all=True,
                       append_images=images[1:], **kwargs)


def adjust_widths(images, resample=PIL.Image.Resampling.LANCZOS):
    """a callback for images_to_pdf() that rescales every image to the
    narrowest width.  (if you use Preview on Mac like me you know how
    jarring the pages can look when images have different widths...)

    optional argument 'resample' is passed to the resize() method.
    defaults to LANCZOS which seems to have the highest downscaling
    quality and slowest perf.

    see:
        https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize
        https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters
        https://python-pillow.org/pillow-perf/
    """
    # find the narrowest width
    min_width = min(width for width, height in (im.size for im in images))
    new_images = []
    for image in images:
        width, height = image.size
        # find a new_height that keeps the aspect ratio
        # note how (roughly) min_width / new_height == width / height
        new_height = round(height * (min_width / width))
        new_size = (min_width, new_height)
        new_images.append(image.resize(new_size, resample=resample))
    return new_images


# istg i never remember if it is ${var#prefix} or ${var%suffix}:
# https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html
def main():
    import argparse
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
        image conversion + making image-based PDF

        examples:
          image to pdf:

            python3 -m imgconv *.jpg out.pdf
            python3 -m imgconv --adjust-widths --grayscale *.jpg out.pdf

          HEIF file to image: (quoting everything in case the files
          have evil space characters)

            for img in ./*.heif; do
              python3 -m imgconv "$img" "${img%.*}.jpg"
            done

            # alternative
            for img in ./*.heic; do
              python3 -m imgconv "$img" "${img%.*}.jpg"
            done
        """))
    parser.add_argument('src', nargs='+',
                        help=("source files. must be precisely ONE HEIF "
                              "file when dst is an image, or one or more "
                              "HEIF or Pillow-supported image files when "
                              "dst is a PDF"))
    parser.add_argument('dst',
                        help=("destination file, could be PDF or any image "
                              "type Pillow supports (IMG, PNG, etc.) "
                              "the type is automatically inferred from the "
                              "file path"))
    parser.add_argument('--quality', default=None,
                        help=("quality of the exported JPEG. MAY apply if "
                              "Pillow recognizes your image extension as "
                              "JPEG. DO NOT SPECIFY THIS when dst is a PDF. "
                              "default to 75"))
    parser.add_argument('--grayscale', action='store_true',
                        help=("switch for converting images to the L "
                              "(luminance) mode (without alpha channel!)"))
    parser.add_argument('--adjust-widths', action='store_true',
                        help=("switch for rescaling every page of the "
                              "produced PDF using adjust_widths(). (if dst "
                              "is an image, this switch is ignored"))

    args = parser.parse_args()
    if has_extension(args.dst, ['.pdf']):
        if args.quality is not None:
            raise ValueError('--quality does not apply to PDF')
        filters = []
        if args.adjust_widths:
            filters.append(adjust_widths)
        if args.grayscale:
            filters.append(lambda images: [im.convert('L') for im in images])
        images_to_pdf(args.src, args.dst, filters)
    else:
        if len(args.src) != 1:
            raise ValueError('can only supply one source file when '
                             'converting HEIF to JPEG')
        src = args.src[0]
        if has_extension(src, ['.heif', '.heic']):
            im = load_heif(src)
        else:
            with PIL.Image.open(src) as im:
                im.load()
        if args.grayscale:
            im = im.convert('L')
        quality = args.quality if args.quality is not None else 75
        im.save(args.dst, quality=quality)


if __name__ == '__main__':
    main()
