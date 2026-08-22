// Tool Execution Queue (Phase 7-T5-A: Tool Executor Core Runtime).
//
// Phase 7-T5-A: FIFO queue for pending tool executions.
// Distinct from:
//   - Phase 7-T0 ToolDefinition / ToolResult (contracts)
//   - Phase 7-T1 ToolRegistry (storage)
//   - Phase 7-T2 ToolAdapter (translation binding)
//   - Phase 7-T4 ToolExecutionSchema (request / record / status / events)
//
// Phase 7-T5-A frozen contract:
//   - enqueue(requestId): adds to tail
//   - dequeue(): removes + returns from head (FIFO)
//   - remove(requestId): removes by id
//   - size(): number of pending requests
//   - has(requestId): check existence
//   - list(): array snapshot (insertion order)
//
// Phase 7-T5-A strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - FIFO with deterministic order (insertion order is the canonical order)

export class ToolExecutionQueue {
  private readonly items: string[] = []

  /** Phase 7-T5-A: enqueue a requestId (FIFO). */
  enqueue(requestId: string): void {
    if (typeof requestId !== 'string' || requestId.length === 0) return
    if (this.items.includes(requestId)) return  // idempotent
    this.items.push(requestId)
  }

  /** Phase 7-T5-A: dequeue from head. Returns undefined when empty. */
  dequeue(): string | undefined {
    return this.items.shift()
  }

  /** Phase 7-T5-A: remove a requestId by value. Returns boolean. */
  remove(requestId: string): boolean {
    const idx = this.items.indexOf(requestId)
    if (idx === -1) return false
    this.items.splice(idx, 1)
    return true
  }

  /** Phase 7-T5-A: number of pending requests. */
  size(): number {
    return this.items.length
  }

  /** Phase 7-T5-A: check if a requestId is queued. */
  has(requestId: string): boolean {
    return this.items.includes(requestId)
  }

  /** Phase 7-T5-A: snapshot (insertion order, defensive copy). */
  list(): string[] {
    return [...this.items]
  }

  /** Phase 7-T5-A: clear all (testing helper). */
  clear(): void {
    this.items.length = 0
  }
}
