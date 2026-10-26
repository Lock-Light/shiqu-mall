package org.javaup.commerce;

import java.util.Map;
import org.javaup.dto.Result;
import org.springframework.web.bind.annotation.*;

@RestController
public class CommerceSeckillController {
  final CommerceSeckill service;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceSeckillController(CommerceSeckill service) {
    this.service = service;
  }

  @PostMapping("/merchant/activities")
  public Result<?> publish(@RequestBody Map<String, Object> form) {
    return Result.ok(CommerceController.view(service.publish(form)));
  }

  @PostMapping("/trade/activities/{id}/reserve")
  public Result<?> reserve(@PathVariable long id, @RequestBody Map<String, Object> form) {
    return Result.ok(CommerceController.view(service.reserve(id, form)));
  }

  @PostMapping("/merchant/activities/{id}/stop")
  public Result<?> stop(@PathVariable long id) {
    return Result.ok(CommerceController.view(service.stop(id)));
  }

  @GetMapping("/trade/activities/{id}/result")
  public Result<?> result(@PathVariable long id, @RequestParam long reservationId) {
    return Result.ok(CommerceController.view(service.result(id, reservationId)));
  }
}
