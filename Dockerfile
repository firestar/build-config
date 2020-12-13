FROM python:3.8

RUN pip install kubernetes
RUN pip install Jinja2

RUN mkdir ~/.kube/
COPY kube/config /kube/config
COPY build-configs.py /
WORKDIR /

CMD python /build-configs.py