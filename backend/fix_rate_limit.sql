-- Clean up orphaned registration requests
-- Run this SQL directly in your Cloud SQL database

-- Option 1: Delete all requests without reviewed_at (orphaned)
DELETE FROM registration_requests
WHERE reviewed_at IS NULL
AND created_at < DATE_SUB(NOW(), INTERVAL 1 HOUR);

-- Option 2: Delete all requests older than 1 hour regardless of status
-- DELETE FROM registration_requests
-- WHERE created_at < DATE_SUB(NOW(), INTERVAL 1 HOUR);

-- Check remaining requests
SELECT COUNT(*) as total_requests,
       SUM(CASE WHEN reviewed_at IS NOT NULL THEN 1 ELSE 0 END) as reviewed,
       SUM(CASE WHEN reviewed_at IS NULL THEN 1 ELSE 0 END) as orphaned
FROM registration_requests;
