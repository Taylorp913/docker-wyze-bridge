FROM python:3.9-slim
RUN apt-get update && apt-get install ffmpeg unzip g++ -y && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip3 install requests wyzecam wyze_sdk bottle
ADD https://github.com/nblavoie/wyzecam-api/raw/master/wyzecam-sdk/TUTK_IOTC_Platform_14W42P1.zip /tmp/tutk.zip
RUN unzip /tmp/tutk.zip -d /tmp/tutk/ && cd /tmp/tutk/Lib/Linux/x64/ && g++ -fpic -shared -Wl,--whole-archive libAVAPIs.a libIOTCAPIs.a -Wl,--no-whole-archive -o libIOTCAPIs_ALL.so && cp libIOTCAPIs_ALL.so /usr/local/lib/ && rm -rf /tmp/*
RUN mkdir -p /tokens
WORKDIR /app
COPY wyze_bridge.py .
CMD [ "python3", "wyze_bridge.py" ]