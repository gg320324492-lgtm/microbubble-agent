// Tool Execution Events (Phase 7-T5-A: Tool Executor Core Runtime).
//
// Phase 7-T5-A: typed trace event emitter for Tool Execution lifecycle.
// Distinct from:
//   - Phase 7-T4 ToolExecutionTraceEvent (Phase 7-T4 contracts)
//   - Phase 7-T4 ToolExecutionTracePayload
//
// Phase 7-T5-A frozen contract:
//   - ToolExecutionEventEmitter extends EventEmitter (Node-style)
//   - emit('tool_execution_start' | 'tool_execution_progress' |
//          'tool_execution_complete' | 'tool_execution_error', payload)
//   - payload is validated via isValidToolExecutionTracePayload (Phase 7-T4)
//
// Phase 7-T5-A strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - Compatible with Phase 6-C1 TraceTimeline component

import { EventEmitter } from 'node:events'

import {
  type ToolExecutionTraceEvent,
  type ToolExecutionTracePayload,
  isValidToolExecutionTracePayload,
  isValidToolExecutionTraceEvent
} from '../../../shared/tools/execution-schema'

type Listener = (payload: ToolExecutionTracePayload) => void

export class ToolExecutionEventEmitter extends EventEmitter {
  /** Phase 7-T5-A: emit a validated trace event. Throws if payload invalid. */
  emitTrace(event: ToolExecutionTraceEvent, payload: ToolExecutionTracePayload): boolean {
    if (!isValidToolExecutionTraceEvent(event)) {
      throw new Error(`ToolExecutionEventEmitter: invalid event '${event}' (Phase 7-T5-A strict)`)
    }
    if (!isValidToolExecutionTracePayload(payload)) {
      throw new Error(`ToolExecutionEventEmitter: invalid payload for event '${event}' (Phase 7-T5-A strict)`)
    }
    return super.emit(event, payload)
  }

  /** Phase 7-T5-A: subscribe to a trace event with a typed listener. */
  onTrace(event: ToolExecutionTraceEvent, listener: Listener): this {
    return super.on(event, listener)
  }

  /** Phase 7-T5-A: remove a trace event listener. */
  offTrace(event: ToolExecutionTraceEvent, listener: Listener): this {
    return super.off(event, listener)
  }

  /** Phase 7-T5-A: remove all listeners (testing helper). */
  removeAllTraceListeners(event?: ToolExecutionTraceEvent): this {
    return event ? super.removeAllListeners(event) : super.removeAllListeners()
  }

  /** Phase 7-T5-A: count listeners (testing helper). */
  listenerCountFor(event: ToolExecutionTraceEvent): number {
    return super.listenerCount(event)
  }
}
