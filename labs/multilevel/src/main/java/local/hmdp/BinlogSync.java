package local.hmdp;

import com.alibaba.otter.canal.client.*;
import com.alibaba.otter.canal.protocol.*;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.*;
import java.util.concurrent.*;

@Component
@ConditionalOnProperty(name="lab.canal.enabled",havingValue="true")
public class BinlogSync {
    private static final Logger log=LoggerFactory.getLogger(BinlogSync.class);
    final CacheLab lab;
    final ExecutorService worker=Executors.newSingleThreadExecutor();
    volatile boolean running=true;
    public BinlogSync(CacheLab lab){this.lab=lab;}
    @PostConstruct public void start(){worker.submit(this::consume);}
    void consume(){
        while(running){
            CanalConnector client=CanalConnectors.newSingleConnector(new InetSocketAddress("canal",11111),"example","","");
            try{
                client.connect();client.subscribe("cache_lab\\.tb_shop");client.rollback();
                while(running){
                    Message message=client.getWithoutAck(100);
                    if(message.getId()==-1||message.getEntries().isEmpty()){Thread.sleep(100);continue;}
                    for(CanalEntry.Entry entry:message.getEntries()){
                        if(entry.getEntryType()!=CanalEntry.EntryType.ROWDATA)continue;
                        CanalEntry.RowChange change=CanalEntry.RowChange.parseFrom(entry.getStoreValue());
                        if(change.getIsDdl())continue;
                        for(CanalEntry.RowData row:change.getRowDatasList()){
                            var columns=change.getEventType()==CanalEntry.EventType.DELETE?row.getBeforeColumnsList():row.getAfterColumnsList();
                            for(CanalEntry.Column column:columns)if("id".equals(column.getName())){
                                long id=Long.parseLong(column.getValue());
                                lab.cache.invalidate(id);lab.redis.delete("multilevel:shop:"+id);
                                invalidate("http://app2:8080/internal/invalidate/"+id,true);
                                invalidate("http://edge/_invalidate?id="+id,false);
                                lab.redis.opsForValue().set("lab:canal:last-id",String.valueOf(id));
                                log.info("Canal invalidated id={} in Redis, two JVMs and OpenResty",id);
                            }
                        }
                    }
                    client.ack(message.getId());
                }
            }catch(Exception e){
                if(running)log.warn("Canal retry: {}",e.toString());
                try{Thread.sleep(1000);}catch(InterruptedException ignored){Thread.currentThread().interrupt();}
            }finally{try{client.disconnect();}catch(Exception ignored){}}
        }
    }
    void invalidate(String url,boolean post)throws Exception{
        HttpURLConnection conn=(HttpURLConnection)new URI(url).toURL().openConnection();
        conn.setConnectTimeout(2000);conn.setReadTimeout(2000);conn.setRequestProperty("X-Lab-Key","plus-cache-internal");
        if(post)conn.setRequestMethod("POST");
        try{if(conn.getResponseCode()!=200)throw new IllegalStateException("invalidation failed: "+url);}finally{conn.disconnect();}
    }
    @PreDestroy public void stop(){running=false;worker.shutdownNow();}
}
