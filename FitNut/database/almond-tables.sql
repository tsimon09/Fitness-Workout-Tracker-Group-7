CREATE TABLE IF NOT EXISTS almond_memory (
 user_id INT PRIMARY KEY, cuisines JSON NOT NULL, cooking_minutes INT NULL, food_budget VARCHAR(100),
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_conversations (
 conversation_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, title VARCHAR(100) NOT NULL, constraints_json JSON NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_messages (
 message_id INT AUTO_INCREMENT PRIMARY KEY, conversation_id INT NOT NULL, role ENUM('user','assistant') NOT NULL,
 content TEXT NOT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (conversation_id) REFERENCES almond_conversations(conversation_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_recipes (
 recipe_id INT AUTO_INCREMENT PRIMARY KEY, conversation_id INT NOT NULL, user_id INT NOT NULL, recipe JSON NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (conversation_id) REFERENCES almond_conversations(conversation_id) ON DELETE CASCADE,
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_favorites (
 favorite_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, recipe JSON NOT NULL,
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_food_evidence (
 food_id INT PRIMARY KEY, evidence JSON NOT NULL, reviewed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (food_id) REFERENCES food_catalog(food_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_food_observations (
 food_id INT PRIMARY KEY, observation JSON NOT NULL, fetched_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (food_id) REFERENCES food_catalog(food_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_requests (
 request_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, conversation_id INT NOT NULL,
 request_key VARCHAR(80) NOT NULL, payload_hash CHAR(64) NOT NULL, status ENUM('pending','done','failed') NOT NULL DEFAULT 'pending',
 response JSON NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_almond_request (user_id,request_key),
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY (conversation_id) REFERENCES almond_conversations(conversation_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_budgets (
 scope VARCHAR(20) PRIMARY KEY, cap_usd DECIMAL(14,9) NOT NULL, spent_usd DECIMAL(14,9) NOT NULL DEFAULT 0,
 reserved_usd DECIMAL(14,9) NOT NULL DEFAULT 0
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_usage (
 usage_id INT AUTO_INCREMENT PRIMARY KEY, request_id INT NULL, user_id INT NOT NULL, scope VARCHAR(20) NOT NULL,
 model VARCHAR(150) NOT NULL, reserved_usd DECIMAL(14,9) NOT NULL, actual_usd DECIMAL(14,9) NULL,
 status ENUM('reserved','settled') NOT NULL DEFAULT 'reserved', upstream_id VARCHAR(150), usage_json JSON,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY (scope) REFERENCES almond_budgets(scope)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_evaluations (
 run_id INT AUTO_INCREMENT PRIMARY KEY, model VARCHAR(150) NOT NULL, qualified BOOLEAN NOT NULL DEFAULT FALSE,
 report JSON NOT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS almond_switch (
 switch_id INT PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;
