// Convert an iPhone HDR (HLG) clip to SDR Rec.709 ProRes 422 HQ using Apple's own HDR->SDR tone mapping (what Photos/QuickTime show).
import AVFoundation
let a = CommandLine.arguments; let PIXFMT = a.count > 3 && a[3] == "bgra" ? kCVPixelFormatType_32BGRA : kCVPixelFormatType_422YpCbCr10BiPlanarVideoRange; let src = URL(fileURLWithPath: a[1]), dst = URL(fileURLWithPath: a[2])
try? FileManager.default.removeItem(at: dst)
let asset = AVURLAsset(url: src)
let sem = DispatchSemaphore(value: 0)
var KEEP: [AnyObject] = []   // hold reader/writer alive for the async callbacks
Task {
  let vt = try! await asset.loadTracks(withMediaType: .video)[0]
  let at = try! await asset.loadTracks(withMediaType: .audio).first
  let size = try! await vt.load(.naturalSize); let xf = try! await vt.load(.preferredTransform)
  let reader = try! AVAssetReader(asset: asset); let writer = try! AVAssetWriter(outputURL: dst, fileType: .mov)
  let c709: [String: Any] = [AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2, AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2, AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2]
  let vout = AVAssetReaderTrackOutput(track: vt, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: PIXFMT, AVVideoColorPropertiesKey: c709])
  vout.alwaysCopiesSampleData = false; reader.add(vout)
  let vin = AVAssetWriterInput(mediaType: .video, outputSettings: [AVVideoCodecKey: AVVideoCodecType.proRes422HQ, AVVideoWidthKey: Int(size.width), AVVideoHeightKey: Int(size.height), AVVideoColorPropertiesKey: c709])
  vin.transform = xf; vin.expectsMediaDataInRealTime = false; writer.add(vin)
  var aout: AVAssetReaderTrackOutput? = nil; var ain: AVAssetWriterInput? = nil
  if let at = at { let o = AVAssetReaderTrackOutput(track: at, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 24, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false])
    reader.add(o); aout = o
    let i = AVAssetWriterInput(mediaType: .audio, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 24, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false, AVSampleRateKey: 48000, AVNumberOfChannelsKey: 2])
    i.expectsMediaDataInRealTime = false; writer.add(i); ain = i }
  KEEP = [reader, writer]
  if !reader.startReading() { print("reader fail:", reader.error ?? "?"); exit(2) }
  if !writer.startWriting() { print("writer fail:", writer.error ?? "?"); exit(3) }
  writer.startSession(atSourceTime: .zero)
  let g = DispatchGroup()
  g.enter(); vin.requestMediaDataWhenReady(on: DispatchQueue(label: "v")) { while vin.isReadyForMoreMediaData { if let b = vout.copyNextSampleBuffer() { vin.append(b) } else { vin.markAsFinished(); g.leave(); return } } }
  if let ain = ain, let aout = aout { g.enter(); ain.requestMediaDataWhenReady(on: DispatchQueue(label: "a")) { while ain.isReadyForMoreMediaData { if let b = aout.copyNextSampleBuffer() { ain.append(b) } else { ain.markAsFinished(); g.leave(); return } } } }
  g.notify(queue: .main) { writer.finishWriting { print("done", writer.status.rawValue, writer.error?.localizedDescription ?? ""); sem.signal() } }
}
while sem.wait(timeout: .now() + 0.2) == .timedOut { RunLoop.main.run(until: Date().addingTimeInterval(0.2)) }
