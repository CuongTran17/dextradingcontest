-- Tạo database mới nếu chưa có
CREATE DATABASE IF NOT EXISTS vnstock_data DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE vnstock_data;

-- Tạo bảng lưu trữ dữ liệu nến cuối ngày (EOD)
-- Cache overview doanh nghiệp (dữ liệu cơ bản + định giá chuẩn hóa)
CREATE TABLE IF NOT EXISTS company_overview_cache (
    symbol VARCHAR(50) PRIMARY KEY,
    payload_json LONGTEXT NOT NULL,
    source VARCHAR(64) NOT NULL DEFAULT 'vnstock',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_company_overview_cache_updated_at (updated_at)
);

-- Cache báo cáo tài chính theo loại report
CREATE TABLE IF NOT EXISTS financial_report_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    report_type VARCHAR(20) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    payload_json LONGTEXT NOT NULL,
    source VARCHAR(64) NOT NULL DEFAULT 'vnstock',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_financial_report_cache_symbol_type (symbol, report_type),
    INDEX idx_financial_report_cache_symbol (symbol),
    INDEX idx_financial_report_cache_updated_at (updated_at)
);

-- Cache dữ liệu technical theo tham số truy vấn
-- Cache tin tức theo mã
CREATE TABLE IF NOT EXISTS news_cache (
    symbol VARCHAR(50) PRIMARY KEY,
    item_count INT NOT NULL DEFAULT 0,
    payload_json LONGTEXT NOT NULL,
    source VARCHAR(64) NOT NULL DEFAULT 'vnstock',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_news_cache_updated_at (updated_at)
);

-- Cache sự kiện doanh nghiệp theo mã
CREATE TABLE IF NOT EXISTS events_cache (
    symbol VARCHAR(50) PRIMARY KEY,
    item_count INT NOT NULL DEFAULT 0,
    payload_json LONGTEXT NOT NULL,
    source VARCHAR(64) NOT NULL DEFAULT 'vnstock',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_events_cache_updated_at (updated_at)
);

-- Tài khoản người dùng cho chức năng đăng ký / đăng nhập
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20) NULL UNIQUE,
    fullname VARCHAR(255) NOT NULL,
    avatar_data LONGTEXT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user','premium','admin') NOT NULL DEFAULT 'user',
    is_locked TINYINT(1) NOT NULL DEFAULT 0,
    locked_reason VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_created_at (created_at)
);
