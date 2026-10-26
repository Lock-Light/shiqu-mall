package org.javaup.commerce;

import org.javaup.dto.Result;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CommerceAdvice {
  @ExceptionHandler(org.apache.dubbo.rpc.RpcException.class)
  public ResponseEntity<?> unavailable(org.apache.dubbo.rpc.RpcException exception) {
    return ResponseEntity.status(503).body(Result.fail("用户或门店服务暂不可用，请稍后重试"));
  }
  @ExceptionHandler(CommerceProblem.class)
  public ResponseEntity<?> problem(CommerceProblem problem) {
    return ResponseEntity.status(problem.status).body(Result.fail(problem.getMessage()));
  }
}
