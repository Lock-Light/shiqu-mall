local id = ngx.var.uri:match("/(%d+)$")
if not id then return ngx.exit(400) end
local key = "shop:" .. id
local hit = ngx.shared.shop_cache:get(key)
if hit then ngx.header["X-Cache-Layer"]="OpenResty"; ngx.header.content_type="application/json"; ngx.say(hit); return end
local redis = require "resty.redis"
local conn = redis:new(); conn:set_timeout(1500)
local ok = conn:connect("redis",6379)
local value
if ok then
  conn:auth("cache-local")
  value=conn:get("multilevel:shop:"..id)
end
if value and value ~= ngx.null then
  ngx.header["X-Cache-Layer"]="Redis"
else
  local res=ngx.location.capture("/internal/shop/"..id)
  if res.status ~= 200 then return ngx.exit(res.status) end
  value=res.body
  ngx.header["X-Cache-Layer"]=res.header["X-Cache-Layer"] or "Tomcat"
  if ok then conn:setex("multilevel:shop:"..id,60,value) end
end
if ok then conn:set_keepalive(10000,20) end
ngx.shared.shop_cache:set(key,value,60)
ngx.header.content_type="application/json"; ngx.say(value)
