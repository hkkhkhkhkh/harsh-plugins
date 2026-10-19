// Per-frame person matte for a clip (Apple Vision person segmentation). Writes raw 8-bit gray 1080x1920 frames to stdout,
// one per source frame, in order. Usage: personmatte IN.mov [accurate|balanced] | ffmpeg -f rawvideo -pix_fmt gray -s 1080x1920 ...
import AVFoundation
import Vision
import CoreImage
import QuartzCore
import AppKit
let a = CommandLine.arguments; let src = URL(fileURLWithPath: a[1])
let quality: VNGeneratePersonSegmentationRequest.QualityLevel = (a.count > 2 && a[2] == "balanced") ? .balanced : .accurate
let W = 1080, H = 1920
let asset = AVURLAsset(url: src); let sem = DispatchSemaphore(value: 0)
let ctx = CIContext(options: [.workingColorSpace: NSNull(), .outputColorSpace: NSNull()])
var out = [UInt8](repeating: 0, count: W * H); var n = 0
Task {
  let vt = try! await asset.loadTracks(withMediaType: .video)[0]
  let reader = try! AVAssetReader(asset: asset)
  let vout = AVAssetReaderTrackOutput(track: vt, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                                                                  kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H])
  vout.alwaysCopiesSampleData = false; reader.add(vout)
  if !reader.startReading() { FileHandle.standardError.write("reader fail\n".data(using: .utf8)!); exit(2) }
  let req = VNGeneratePersonSegmentationRequest(); req.qualityLevel = quality; req.outputPixelFormat = kCVPixelFormatType_OneComponent8
  let so = FileHandle.standardOutput
  while let sb = vout.copyNextSampleBuffer() {
    guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
    let h = VNImageRequestHandler(cvPixelBuffer: pb, options: [:])
    var wrote = false
    if (try? h.perform([req])) != nil, let m = req.results?.first?.pixelBuffer {
      let ci = CIImage(cvPixelBuffer: m)
      let sx = CGFloat(W) / ci.extent.width, sy = CGFloat(H) / ci.extent.height
      let scaled = ci.applyingFilter("CILanczosScaleTransform", parameters: ["inputScale": sy, "inputAspectRatio": sx / sy])
      out.withUnsafeMutableBytes { p in
        ctx.render(scaled, toBitmap: p.baseAddress!, rowBytes: W, bounds: CGRect(x: 0, y: 0, width: W, height: H), format: .L8, colorSpace: nil) }
      wrote = true
    }
    if !wrote { out = [UInt8](repeating: 0, count: W * H) }
    so.write(Data(out)); n += 1
    if n % 300 == 0 { FileHandle.standardError.write("frames \(n)\n".data(using: .utf8)!) }
  }
  FileHandle.standardError.write("done \(n)\n".data(using: .utf8)!); sem.signal()
}
while sem.wait(timeout: .now() + 0.2) == .timedOut { RunLoop.main.run(until: Date().addingTimeInterval(0.2)) }
