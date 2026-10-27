// An AWS SDK-style error whose message holds an ARN, as AccessDenied messages do.
export function awsError(name: string, httpStatusCode: number): Error {
  return Object.assign(
    new Error("User: arn:aws:sts::account-id:assumed-role/lusot-role/session is not authorized to perform this action"),
    { name, $metadata: { httpStatusCode } },
  );
}
