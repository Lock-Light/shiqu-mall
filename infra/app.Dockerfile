FROM maven:3.9.11-eclipse-temurin-17
ENV JAVA_TOOL_OPTIONS="-Xmx512m -XX:ActiveProcessorCount=2 -Duser.timezone=Asia/Shanghai"
ENV TZ=Asia/Shanghai UPLOAD_DIR=/uploads
WORKDIR /app
COPY hmdp-core-service/target/hmdp-core-service-0.0.1-SNAPSHOT.jar app.jar
ENTRYPOINT ["java","-jar","app.jar","--spring.profiles.active=local","--spring.config.additional-location=file:/config/"]
