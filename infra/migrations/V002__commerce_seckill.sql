CREATE TABLE IF NOT EXISTS mall_seckill_activity (
 id BIGINT PRIMARY KEY, sku_id BIGINT NOT NULL, starts_at DATETIME(3) NOT NULL,
 ends_at DATETIME(3) NOT NULL, status VARCHAR(20) NOT NULL,
 initial_stock INT NOT NULL, created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
 UNIQUE KEY uk_activity_sku(sku_id), INDEX idx_activity_time(status,ends_at,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_seckill_result (
 reservation_id BIGINT PRIMARY KEY, activity_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
 status VARCHAR(20) NOT NULL, reason VARCHAR(100) NOT NULL DEFAULT '',
 sync_pending TINYINT NOT NULL DEFAULT 1, created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
 INDEX idx_seckill_sync(sync_pending,reservation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mall_seckill_limit (
 activity_id BIGINT NOT NULL, user_id BIGINT NOT NULL, reservation_id BIGINT NOT NULL,
 PRIMARY KEY(activity_id,user_id), UNIQUE KEY uk_limit_reservation(reservation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
