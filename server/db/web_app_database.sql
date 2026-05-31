-- Basic database schema for a web application
-- Database schema for web application data
-- This schema is designed to store application-specific data,
-- without user identification, accounts, roles, or session management.

-- 1. Posts table: Example application data
-- This table can be adapted or replaced with actual data structures
-- needed for your web application.
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    content TEXT,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance Optimization: Indexes for application data
CREATE INDEX idx_posts_published ON posts(published_at) WHERE published_at IS NOT NULL;
