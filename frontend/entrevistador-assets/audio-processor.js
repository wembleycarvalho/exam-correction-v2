// AudioWorklet processor — captures PCM 16-bit mono at the context sample rate
// and posts Int16 buffers to the main thread.
class CaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input.length === 0) return true;
    const float32 = input[0]; // mono channel
    // Convert float32 → int16
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
