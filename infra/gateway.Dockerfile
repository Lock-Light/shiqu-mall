FROM maven:3.9.11-eclipse-temurin-17
ENV JAVA_TOOL_OPTIONS="-Xmx256m -XX:ActiveProcessorCount=2 -Duser.timezone=Asia/Shanghai"
ENV TZ=Asia/Shanghai
WORKDIR /app
COPY hmdp-gateway/target/hmdp-gateway-0.0.1-SNAPSHOT.jar app.jar
ENTRYPOINT ["java","-jar","app.jar"]
