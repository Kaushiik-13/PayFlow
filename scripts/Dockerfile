FROM public.ecr.aws/lambda/python:3.12

RUN pip install --no-cache-dir \
    scikit-learn==1.5.0 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    pyarrow==16.1.0

COPY anomaly_lambda.py ${LAMBDA_TASK_ROOT}

CMD [ "anomaly_lambda.lambda_handler" ]