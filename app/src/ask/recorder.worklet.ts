// The AudioWorklet that hands the microphone's audio to the page (Ask's spec §4.7): each render quantum of the first
// channel, copied, since the render buffer is reused, and transferred, so nothing is kept here. It runs in the
// AudioWorkletGlobalScope, which TypeScript's DOM library doesn't describe, so the two globals it uses are declared.
// recorder.ts loads it through Vite's `?worker&url`, so a build serves it as JavaScript.
declare abstract class AudioWorkletProcessor {
  readonly port: MessagePort
}
declare function registerProcessor(name: string, processor: new () => AudioWorkletProcessor): void

class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs: Float32Array[][]): boolean {
    const channel = inputs[0]?.[0]
    if (channel !== undefined && channel.length > 0) {
      const frame = channel.slice()
      this.port.postMessage(frame, [frame.buffer])
    }
    return true // keep running until the page disconnects the node
  }
}

// recorder.ts's PROCESSOR.
registerProcessor('lusot-recorder', RecorderProcessor)
