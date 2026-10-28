// An API Gateway HTTP API (payload 2.0) response with a JSON body.
export interface JsonResponse {
  statusCode: number;
  headers: Record<string, string>;
  body: string;
}

export function json(statusCode: number, body: unknown): JsonResponse {
  return { statusCode, headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
}
