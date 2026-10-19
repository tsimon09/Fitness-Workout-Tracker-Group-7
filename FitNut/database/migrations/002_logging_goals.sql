ALTER TABLE user_profiles MODIFY COLUMN weight_kg DECIMAL(5,2) NULL;
ALTER TABLE user_profiles ADD COLUMN daily_calorie_target DECIMAL(10,2), ADD CONSTRAINT chk_daily_target CHECK (daily_calorie_target IS NULL OR daily_calorie_target > 0);
ALTER TABLE user_profiles ADD COLUMN weekly_activity_minutes DECIMAL(10,2), ADD CONSTRAINT chk_weekly_target CHECK (weekly_activity_minutes IS NULL OR weekly_activity_minutes > 0);
