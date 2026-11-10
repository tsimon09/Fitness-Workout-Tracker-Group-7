-- CSC 4350 Software Engineering
-- Group 7
-- FitNut: Fitness and Nutrition Tracker Application
-- Sprint 2
-- October 6, 2026

-- Create the database for the fitness tracker application
CREATE DATABASE IF NOT EXISTS fitness_tracker;
USE fitness_tracker;

-- Create the AppUser table
CREATE TABLE AppUser (
  user_id INT PRIMARY KEY AUTO_INCREMENT,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  username VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  phone_number CHAR(10),
  city VARCHAR(50),
  state CHAR(2),
  zip_code VARCHAR(10),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

-- Create the UserSession table
CREATE TABLE UserSession (
  session_id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  login_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  logout_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES AppUser(user_id),
  CHECK (logout_at IS NULL OR logout_at >= login_at)
  );

-- Create the ActivityType table
CREATE TABLE ActivityType (
  activity_type_id INT PRIMARY KEY AUTO_INCREMENT,
  activity_name VARCHAR(100) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

-- Create the ActivityEvent table
CREATE TABLE ActivityEvent (
  activity_event_id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  activity_type_id INT NOT NULL,
  custom_activity_name VARCHAR(100),
  time_started DATETIME NOT NULL,
  time_finished DATETIME,
  calories_burned INT,
  FOREIGN KEY (user_id) REFERENCES AppUser(user_id),
  FOREIGN KEY (activity_type_id) REFERENCES ActivityType(activity_type_id),
  CHECK (time_finished IS NULL OR time_finished >= time_started),
  CHECK (calories_burned IS NULL OR calories_burned > 0)
  );

-- Create MealType table
CREATE TABLE MealType (
  meal_type_id INT PRIMARY KEY AUTO_INCREMENT,
  meal_type VARCHAR(20) NOT NULL UNIQUE
  );

-- Create EatingEvent table
CREATE TABLE EatingEvent (
  eating_event_id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  meal_type_id INT NOT NULL,
  event_datetime DATETIME NOT NULL,
  comments TEXT,
  FOREIGN KEY (user_id) REFERENCES AppUser(user_id),
  FOREIGN KEY (meal_type_id) REFERENCES MealType(meal_type_id)
  );

-- Create UnitOfMeasure table
CREATE TABLE UnitOfMeasure (
  unit_id INT PRIMARY KEY AUTO_INCREMENT,
  unit_name VARCHAR(50) NOT NULL UNIQUE,
  unit_abbreviation VARCHAR(10)
  );

-- Create FoodEntry table
CREATE TABLE FoodEntry (
  food_entry_id INT PRIMARY KEY AUTO_INCREMENT,
  eating_event_id INT NOT NULL,
  food_item_name VARCHAR(255) NOT NULL,
  amount_consumed DECIMAL(6,2),
  unit_id INT,
  calories INT,
  protein DECIMAL(5,2),
  carbohydrates DECIMAL(5,2),
  fat DECIMAL(5,2),
  fiber DECIMAL(5,2),
  FOREIGN KEY (eating_event_id) REFERENCES EatingEvent(eating_event_id),
  FOREIGN KEY (unit_id) REFERENCES UnitOfMeasure(unit_id),
  CHECK ((amount_consumed IS NULL AND unit_id IS NULL) OR (amount_consumed IS NOT NULL AND unit_id IS NOT NULL)),
  CHECK (amount_consumed IS NULL OR amount_consumed > 0),
  CHECK (calories IS NULL OR calories >= 0),
  CHECK (protein IS NULL OR protein >= 0),
  CHECK (carbohydrates IS NULL OR carbohydrates >= 0),
  CHECK (fat IS NULL OR fat >= 0),
  CHECK (fiber IS NULL OR fiber >= 0)
  );
  
  
