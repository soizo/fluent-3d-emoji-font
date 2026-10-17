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
let text = "😀👩🏻‍💻🏳️‍🌈1️⃣❤️🌚🫪"
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
    var bounds = [CGRect](repeating: .zero, count: glyphs.count)
    CTFontGetBoundingRectsForGlyphs(actualFont, .horizontal, &glyphs, &bounds, glyphs.count)
    for (glyph, rect) in zip(glyphs, bounds) where glyph != 0 {
        precondition(!rect.isEmpty, "Zero-area glyph bounds: \(glyph)")
    }
    // Spaces may map to .notdef; emoji sequences must survive as five visible glyphs.
    visibleGlyphs += glyphs.filter { $0 != 0 }.count
}
precondition(visibleGlyphs == 7, "CoreText did not shape seven emoji: \(visibleGlyphs)")
let context = CGContext(data: nil, width: 800, height: 160, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
context.setFillColor(CGColor(gray: 1, alpha: 1))
context.fill(CGRect(x: 0, y: 0, width: 800, height: 160))
context.textPosition = CGPoint(x: 32, y: 48)
CTLineDraw(line, context)
// A successful shape is insufficient: every emoji cell must paint colour.
let pixels = context.data!.assumingMemoryBound(to: UInt8.self)
for cell in 0..<7 {
    var coloured = 0
    for y in 0..<160 {
        for x in (32 + cell * 90)..<(32 + (cell + 1) * 90) {
            let i = y * context.bytesPerRow + x * 4
            let rgb = [Int(pixels[i]), Int(pixels[i + 1]), Int(pixels[i + 2])]
            if rgb.max()! - rgb.min()! > 20 { coloured += 1 }
        }
    }
    precondition(coloured > 50, "No colour pixels in emoji cell \(cell)")
}
let image = context.makeImage()!
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, image, nil)
precondition(CGImageDestinationFinalize(dest))
print("CoreText: seven emoji, including new moon face and distorted face, have bounds and colour pixels")
