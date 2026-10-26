package org.javaup.commerce;

import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration
@EnableScheduling
public class CommerceJobs {
  final CommerceService service;

  @org.springframework.beans.factory.annotation.Autowired

  public CommerceJobs(CommerceService service) {
    this.service = service;
  }

  /** 扫描是主动清理；支付/查询还会被动关单，任务延迟不会延长付款期限。 */
  @Scheduled(fixedDelay = 30000, initialDelay = 30000)
  public void expire() {
    try {
      service.expireBatch();
    } catch (Exception e) {
      LoggerFactory.getLogger(getClass()).error("商城到期扫描失败，保留状态供下次重试", e);
    }
  }
}
