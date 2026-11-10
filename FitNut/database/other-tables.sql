-- Combined design: account sessions, meals with foods, activity types/events, and sleep.
USE fitnut;

CREATE TABLE IF NOT EXISTS sessions (
  session_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6),
  KEY idx_sessions_user (user_id),
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT chk_sessions_expiration CHECK (expires_at > created_at),
  CONSTRAINT chk_sessions_revocation CHECK (revoked_at IS NULL OR revoked_at >= created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity_types (
  activity_type_id INT AUTO_INCREMENT PRIMARY KEY,
  activity_name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity_events (
  activity_event_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  activity_type_id INT NOT NULL,
  custom_activity_name VARCHAR(100),
  time_started DATETIME(6) NOT NULL,
  time_finished DATETIME(6) NOT NULL,
  calories_burned DECIMAL(10,2),
  notes TEXT,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_activity_events_user_date (user_id, time_started),
  CONSTRAINT fk_activity_events_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_activity_events_type FOREIGN KEY (activity_type_id) REFERENCES activity_types(activity_type_id),
  CONSTRAINT chk_activity_events_time CHECK (time_finished > time_started),
  CONSTRAINT chk_activity_events_calories CHECK (calories_burned IS NULL OR calories_burned >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS meal_types (
  meal_type_id INT AUTO_INCREMENT PRIMARY KEY,
  meal_type VARCHAR(20) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS eating_events (
  eating_event_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  meal_type_id INT NOT NULL,
  event_datetime DATETIME(6) NOT NULL,
  comments TEXT,
  UNIQUE KEY uq_eating_events (user_id, meal_type_id, event_datetime),
  CONSTRAINT fk_eating_events_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_eating_events_meal FOREIGN KEY (meal_type_id) REFERENCES meal_types(meal_type_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS units_of_measure (
  unit_id INT AUTO_INCREMENT PRIMARY KEY,
  unit_name VARCHAR(30) NOT NULL UNIQUE,
  unit_abbreviation VARCHAR(10)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS food_entries (
  food_entry_id INT AUTO_INCREMENT PRIMARY KEY,
  eating_event_id INT NOT NULL,
  unit_id INT NOT NULL,
  food_name VARCHAR(150) NOT NULL,
  quantity DECIMAL(10,3) NOT NULL,
  calories DECIMAL(10,2),
  protein_g DECIMAL(10,2),
  carbs_g DECIMAL(10,2),
  fat_g DECIMAL(10,2),
  fiber_g DECIMAL(10,2),
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_food_entries_event FOREIGN KEY (eating_event_id) REFERENCES eating_events(eating_event_id) ON DELETE CASCADE,
  CONSTRAINT fk_food_entries_unit FOREIGN KEY (unit_id) REFERENCES units_of_measure(unit_id),
  CONSTRAINT chk_food_entries_name CHECK (CHAR_LENGTH(TRIM(food_name)) > 0),
  CONSTRAINT chk_food_entries_quantity CHECK (quantity > 0),
  CONSTRAINT chk_food_entries_calories CHECK (calories IS NULL OR calories >= 0),
  CONSTRAINT chk_food_entries_protein CHECK (protein_g IS NULL OR protein_g >= 0),
  CONSTRAINT chk_food_entries_carbs CHECK (carbs_g IS NULL OR carbs_g >= 0),
  CONSTRAINT chk_food_entries_fat CHECK (fat_g IS NULL OR fat_g >= 0),
  CONSTRAINT chk_food_entries_fiber CHECK (fiber_g IS NULL OR fiber_g >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sleep_logs (
  sleep_log_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  sleep_start DATETIME(6) NOT NULL,
  sleep_end DATETIME(6) NOT NULL,
  sleep_quality TINYINT UNSIGNED,
  notes TEXT,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_sleep_logs_user_date (user_id, sleep_start),
  CONSTRAINT fk_sleep_logs_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT chk_sleep_dates CHECK (sleep_end > sleep_start),
  CONSTRAINT chk_sleep_quality CHECK (sleep_quality IS NULL OR sleep_quality BETWEEN 1 AND 5)
) ENGINE=InnoDB;
