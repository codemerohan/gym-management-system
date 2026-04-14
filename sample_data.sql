USE gym_db;

-- Insert Mock Trainers
INSERT INTO Trainer (first_name, last_name, specialization, phone) VALUES 
('John', 'Doe', 'Weightlifting', '1234567890'),
('Sarah', 'Connor', 'Cardio & Crossfit', '0987654321');

-- Insert Mock Membership Plans
INSERT INTO Membership_Plan (name, duration_months, price) VALUES 
('Monthly Basic', 1, 50.00),
('Quarterly Pro', 3, 130.00),
('Annual Elite', 12, 450.00);

-- Insert Mock Members
INSERT INTO Member (first_name, last_name, email, phone, join_date, trainer_id) VALUES 
('Alice', 'Smith', 'alice@example.com', '1112223333', CURDATE(), 1),
('Bob', 'Johnson', 'bob@example.com', '4445556666', CURDATE() - INTERVAL 10 DAY, 2),
('Charlie', 'Brown', 'charlie@example.com', '7778889999', CURDATE() - INTERVAL 30 DAY, 1);

-- Insert Mock Subscriptions
INSERT INTO Subscription (member_id, plan_id, start_date, end_date, status) VALUES 
(1, 1, CURDATE(), CURDATE() + INTERVAL 1 MONTH, 'Active'),
(2, 2, CURDATE() - INTERVAL 10 DAY, CURDATE() - INTERVAL 10 DAY + INTERVAL 3 MONTH, 'Active'),
(3, 1, CURDATE() - INTERVAL 30 DAY, CURDATE(), 'Expired');

-- Insert Mock Attendance
INSERT INTO Attendance (member_id, check_in_date, check_in_time) VALUES 
(1, CURDATE(), '08:00:00'),
(2, CURDATE() - INTERVAL 1 DAY, '18:30:00'),
(3, CURDATE() - INTERVAL 2 DAY, '07:15:00'),
(1, CURDATE(), '17:00:00');
