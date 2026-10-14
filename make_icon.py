#!/usr/bin/env python3
"""assets/robot.svg -> PNG seti + Mahmut.icns (bundle'a DOKUNMAZ).

Ikon calisma aninda yuklenir; bundle'in icine kopyalanirsa imza bozulur
ve Erisilebilirlik izni sifirlanir.
"""
import pathlib
import subprocess
import sys

from AppKit import NSBitmapImageRep, NSImage, NSPNGFileType, NSMakeSize

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def render(svg: pathlib.Path, out: pathlib.Path, size: int) -> None:
    img = NSImage.alloc().initWithContentsOfFile_(str(svg))
    if img is None:
        sys.exit(f"HATA: {svg} okunamadi")
    img.setSize_(NSMakeSize(size, size))
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0)
    from AppKit import NSGraphicsContext
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    img.drawInRect_(((0, 0), (size, size)))
    NSGraphicsContext.restoreGraphicsState()
    data = rep.representationUsingType_properties_(NSPNGFileType, {})
    out.write_bytes(bytes(data))


def main() -> None:
    svg = ASSETS / "robot.svg"
    iconset = ASSETS / "Mahmut.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        render(svg, iconset / f"icon_{size}x{size}.png", size)
        half = size // 2
        if half >= 16:
            render(svg, iconset / f"icon_{half}x{half}@2x.png", size)
    render(svg, ASSETS / "icon.png", 1024)
    # menubar: renkli degil, sablon (template) ikon -> karanlik/aydinlik uyumlu
    render(ASSETS / "robot_mono.svg", ASSETS / "menubar.png", 22)
    render(ASSETS / "robot_mono.svg", ASSETS / "menubar@2x.png", 44)
    subprocess.run(["iconutil", "-c", "icns", str(iconset),
                    "-o", str(ASSETS / "Mahmut.icns")], check=True)
    print("hazir:", ASSETS / "Mahmut.icns")


if __name__ == "__main__":
    main()
