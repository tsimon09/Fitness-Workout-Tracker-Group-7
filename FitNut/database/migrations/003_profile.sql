ALTER TABLE user_profiles ADD COLUMN age TINYINT UNSIGNED, ADD CONSTRAINT chk_profile_age CHECK (age IS NULL OR age BETWEEN 1 AND 120);
ALTER TABLE user_profiles ADD COLUMN height_cm DECIMAL(5,2), ADD CONSTRAINT chk_profile_height CHECK (height_cm IS NULL OR (height_cm > 0 AND height_cm <= 300));
ALTER TABLE user_profiles ADD COLUMN fitness_goal ENUM('maintain','lose_weight','gain_muscle','improve_fitness');
ALTER TABLE user_profiles ADD COLUMN fitness_level ENUM('beginner','intermediate','advanced');
ALTER TABLE user_profiles ADD COLUMN dietary_pattern ENUM('no_preference','vegetarian','vegan','pescatarian');
ALTER TABLE user_profiles ADD COLUMN allergy_status ENUM('not_provided','none_reported','listed') NOT NULL DEFAULT 'not_provided';
