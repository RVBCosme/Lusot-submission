// Logs a failure by error name and HTTP status only. AWS error messages can carry ARNs,
// and an ARN carries the account ID, so the message is never logged.
export function logError(msg: string, err: unknown, fields: Record<string, unknown> = {}): void {
  const error = err instanceof Error ? err.name : "unknown";
  const status = (err as { $metadata?: { httpStatusCode?: number } } | undefined)?.$metadata?.httpStatusCode;
  console.error(JSON.stringify({ msg, ...fields, error, status }));
}
