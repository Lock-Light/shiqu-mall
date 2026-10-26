-- 在同一脚本完成库存/限购/恢复索引，避免Java拿到结果后崩溃留下不可恢复的库存预扣。
-- KEYS: stock,buyers,payloads,states,pending,userRate,open（同一活动hash tag）
local existing=redis.call('HGET',KEYS[2],ARGV[1])
if existing then return {1,existing} end
if redis.call('GET',KEYS[7])~='ACTIVE' then return {-5,'活动暂停新增资格，请查询已有订单'} end
local time=redis.call('TIME');local now=time[1]*1000+math.floor(time[2]/1000)
if now<tonumber(ARGV[4]) or now>=tonumber(ARGV[5]) then return {-1,'活动不在进行时间内'} end
local hits=redis.call('INCR',KEYS[6]);if hits==1 then redis.call('PEXPIRE',KEYS[6],2000) end
if hits>6 then return {-2,'请求频繁，请稍后重试'} end
local stock=redis.call('GET',KEYS[1])
if not stock then return {-3,'活动库存未就绪，请稍后查询'} end
if tonumber(stock)<=0 then return {-4,'活动已售罄'} end
redis.call('DECR',KEYS[1])
redis.call('HSET',KEYS[2],ARGV[1],ARGV[2])
redis.call('HSET',KEYS[3],ARGV[2],ARGV[3])
redis.call('HSET',KEYS[4],ARGV[2],'PENDING')
redis.call('ZADD',KEYS[5],now,ARGV[2])
return {0,ARGV[2]}
