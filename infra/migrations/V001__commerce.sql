CREATE TABLE IF NOT EXISTS mall_product (
 id BIGINT PRIMARY KEY, shop_id BIGINT NOT NULL, title VARCHAR(100) NOT NULL,
 category VARCHAR(20) NOT NULL, cover VARCHAR(255) NOT NULL,
 description TEXT NOT NULL, rules TEXT NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
 version BIGINT NOT NULL DEFAULT 1, created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
 INDEX idx_product_browse(status,category,id), INDEX idx_product_shop(shop_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_sku (
 id BIGINT PRIMARY KEY, product_id BIGINT NOT NULL, name VARCHAR(60) NOT NULL,
 price DECIMAL(10,2) NOT NULL, available INT NOT NULL, reserved INT NOT NULL DEFAULT 0,
 sold INT NOT NULL DEFAULT 0, valid_days INT NOT NULL DEFAULT 30,
 sale_mode VARCHAR(16) NOT NULL DEFAULT 'NORMAL', version BIGINT NOT NULL DEFAULT 1,
 CHECK(price > 0), CHECK(available >= 0 AND reserved >= 0 AND sold >= 0), CHECK(valid_days > 0),
 INDEX idx_sku_product(product_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_shop_member (
 user_id BIGINT NOT NULL, shop_id BIGINT NOT NULL, role VARCHAR(16) NOT NULL,
 PRIMARY KEY(user_id,shop_id), CHECK(role IN ('ADMIN','MERCHANT'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_trade_order (
 id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL, shop_id BIGINT NOT NULL, sku_id BIGINT NOT NULL,
 title VARCHAR(100) NOT NULL, sku_name VARCHAR(60) NOT NULL, cover VARCHAR(255) NOT NULL,
 shop_name VARCHAR(100) NOT NULL, rules TEXT NOT NULL, valid_days INT NOT NULL,
 amount DECIMAL(10,2) NOT NULL, status VARCHAR(16) NOT NULL,
 request_key VARCHAR(80) NOT NULL, quote_version VARCHAR(64) NOT NULL,
 created_at DATETIME(3) NOT NULL, expires_at DATETIME(3) NOT NULL,
 paid_at DATETIME(3), closed_at DATETIME(3), used_at DATETIME(3), close_reason VARCHAR(32),
 UNIQUE KEY uk_order_request(user_id,request_key),
 INDEX idx_order_user(user_id,id), INDEX idx_order_shop(shop_id,id),
 INDEX idx_order_expiry(status,expires_at,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_payment_attempt (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
 request_key VARCHAR(80) NOT NULL, outcome VARCHAR(16) NOT NULL,
 amount DECIMAL(10,2) NOT NULL, created_at DATETIME(3) NOT NULL,
 UNIQUE KEY uk_payment_request(user_id,request_key), INDEX idx_payment_order(order_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_redemption (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL, shop_id BIGINT NOT NULL,
 code VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL, expires_at DATETIME(3) NOT NULL,
 used_at DATETIME(3), used_by BIGINT,
 UNIQUE KEY uk_redemption_order(order_id), UNIQUE KEY uk_redemption_code(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_order_event (
 id BIGINT PRIMARY KEY, order_id BIGINT NOT NULL, actor_id BIGINT,
 event_type VARCHAR(32) NOT NULL, detail VARCHAR(255) NOT NULL,
 created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), INDEX idx_event_order(order_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_stock_movement (
 id BIGINT PRIMARY KEY, sku_id BIGINT NOT NULL, order_id BIGINT NOT NULL,
 action VARCHAR(20) NOT NULL, delta INT NOT NULL, actor_id BIGINT,
 created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
 UNIQUE KEY uk_stock_business(sku_id,order_id,action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
