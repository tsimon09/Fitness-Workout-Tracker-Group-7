-- Additive and rerunnable through scripts/init_database.py; no records are replaced.
ALTER TABLE activity_events ADD COLUMN intensity ENUM('low','moderate','high');
ALTER TABLE activity_events ADD COLUMN distance_km DECIMAL(10,3), ADD CONSTRAINT chk_activity_distance CHECK (distance_km IS NULL OR distance_km >= 0);
ALTER TABLE activity_events ADD COLUMN set_count INT, ADD CONSTRAINT chk_activity_sets CHECK (set_count IS NULL OR set_count > 0);
ALTER TABLE activity_events ADD COLUMN rep_count INT, ADD CONSTRAINT chk_activity_reps CHECK (rep_count IS NULL OR rep_count > 0);
ALTER TABLE activity_events ADD COLUMN calorie_source ENUM('manual','estimated') NOT NULL DEFAULT 'manual';
ALTER TABLE activity_events ADD COLUMN body_weight_kg DECIMAL(5,2), ADD CONSTRAINT chk_activity_weight CHECK (body_weight_kg IS NULL OR body_weight_kg > 0);
ALTER TABLE activity_events ADD COLUMN met_value DECIMAL(4,2), ADD CONSTRAINT chk_activity_met CHECK (met_value IS NULL OR met_value > 0);
ALTER TABLE food_entries ADD COLUMN food_id INT, ADD CONSTRAINT fk_food_catalog FOREIGN KEY (food_id) REFERENCES food_catalog(food_id) ON DELETE SET NULL;
ALTER TABLE food_entries ADD COLUMN serving_grams DECIMAL(10,3), ADD CONSTRAINT chk_food_serving CHECK (serving_grams IS NULL OR serving_grams > 0);
