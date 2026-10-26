-- MySQL终态驱动幂等确认/释放；旧消息不得删除较新预占的限购资格。
local old=redis.call('HGET',KEYS[4],ARGV[1])
if not old then return -1 end
if ARGV[3]=='CREATED' then
  if old=='PENDING' then redis.call('HSET',KEYS[4],ARGV[1],'COMMITTED') end
else
  if old~='RELEASED' then
    redis.call('HSET',KEYS[4],ARGV[1],'RELEASED')
    redis.call('INCR',KEYS[1])
    if redis.call('HGET',KEYS[2],ARGV[2])==ARGV[1] then redis.call('HDEL',KEYS[2],ARGV[2]) end
  end
end
redis.call('ZREM',KEYS[5],ARGV[1])
return 1
