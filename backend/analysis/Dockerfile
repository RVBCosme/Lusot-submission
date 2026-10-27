# The analysis Lambda (C22): AWS's Python 3.13 base image, pinned by digest (Oct 28).
FROM public.ecr.aws/lambda/python:3.13@sha256:e0237850eecd760896365e768bac1526ea01098e325fa590e5bc735b26d5dbb9

# Runtime dependencies exactly as uv.lock pins them, each checked against its hash.
COPY requirements.lock.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir --require-hashes -r ${LAMBDA_TASK_ROOT}/requirements.lock.txt

# The package, with its vendored YuNet model.
COPY src/lusot_analysis ${LAMBDA_TASK_ROOT}/lusot_analysis

CMD ["lusot_analysis.handler.handler"]
