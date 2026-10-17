// Native CoreText smoke test. Run: swift scripts/check_macos.swift FONT OUTPUT.png
import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
precondition(args.count == 3, "Expected font path and output PNG")
let provider = CGDataProvider(url: URL(fileURLWithPath: args[1]) as CFURL)!
let graphicsFont = CGFont(provider)!
let font = CTFontCreateWithGraphicsFont(graphicsFont, 90, nil, nil)
let text = "😀👩🏻‍💻🏳️‍🌈1️⃣❤️"
let attrs: [NSAttributedString.Key: Any] = [NSAttributedString.Key(kCTFontAttributeName as String): font]
let line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attrs))
let runs = CTLineGetGlyphRuns(line) as! [CTRun]
var visibleGlyphs = 0
for run in runs {
    let attributes = CTRunGetAttributes(run) as NSDictionary
    let actualFont = attributes[kCTFontAttributeName] as! CTFont
    precondition(CTFontCopyPostScriptName(actualFont) == CTFontCopyPostScriptName(font), "Unexpected system fallback")
    var glyphs = [CGGlyph](repeating: 0, count: CTRunGetGlyphCount(run))
    CTRunGetGlyphs(run, CFRange(location: 0, length: 0), &glyphs)
    // Spaces may map to .notdef; emoji sequences must survive as five visible glyphs.
    visibleGlyphs += glyphs.filter { $0 != 0 }.count
}
precondition(visibleGlyphs == 5, "CoreText did not shape five emoji: \(visibleGlyphs)")
let context = CGContext(data: nil, width: 640, height: 160, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
context.setFillColor(CGColor(gray: 1, alpha: 1))
context.fill(CGRect(x: 0, y: 0, width: 640, height: 160))
context.textPosition = CGPoint(x: 32, y: 48)
CTLineDraw(line, context)
let image = context.makeImage()!
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, image, nil)
precondition(CGImageDestinationFinalize(dest))
print("CoreText: five emoji shaped with custom font; preview saved")
