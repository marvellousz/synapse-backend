-- AlterTable
-- Add passwordHash for auth (existing users get empty string and cannot log in until they sign up again)
ALTER TABLE "User" ADD COLUMN "passwordHash" TEXT NOT NULL DEFAULT '';
