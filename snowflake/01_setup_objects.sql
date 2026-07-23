-- ============================================================================
-- BoC Economics — Snowflake object setup (Phase 1)
--
-- Creates NEW, ISOLATED objects for this project. It does NOT touch any of the
-- existing badge warehouses/databases. Run once, top to bottom, in a worksheet.
--
-- Roles: the blocks below switch role with `use role`. You have ACCOUNTADMIN
-- available (even though you usually work as SYSADMIN), so this runs in one go.
--   [ACCOUNTADMIN] creating/granting the role — needs ACCOUNTADMIN.
--   [SYSADMIN]     the warehouse / database / schemas.
-- Replace <YOUR_SNOWFLAKE_USER> with your login name before running.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- [ACCOUNTADMIN] Dedicated project role (isolated from badge work)
-- ---------------------------------------------------------------------------
use role accountadmin;

create role if not exists BOC_ROLE
  comment = 'BoC Economics dbt project';

grant role BOC_ROLE to user <YOUR_SNOWFLAKE_USER>;
grant role BOC_ROLE to role SYSADMIN;   -- so SYSADMIN can manage under it

-- ---------------------------------------------------------------------------
-- [SYSADMIN] Warehouse, database, schemas — all new and isolated
-- ---------------------------------------------------------------------------
use role sysadmin;

create warehouse if not exists BOC_WH
  warehouse_size = 'XSMALL'
  auto_suspend = 60           -- seconds; protects trial credits
  auto_resume = true
  initially_suspended = true
  comment = 'BoC Economics — XS, auto-suspend 60s';

create database if not exists BOC_DB
  comment = 'BoC Economics dbt project';

create schema if not exists BOC_DB.BOC_RAW;          -- ingestion lands here
create schema if not exists BOC_DB.BOC_ANALYTICS;    -- dbt target: snowflake
create schema if not exists BOC_DB.BOC_ANALYTICS_CI; -- dbt target: snowflake_ci

-- ---------------------------------------------------------------------------
-- [SYSADMIN] Grant the project role everything it needs
-- ---------------------------------------------------------------------------
grant usage, operate on warehouse BOC_WH to role BOC_ROLE;
grant usage, create schema on database BOC_DB to role BOC_ROLE;

grant all on schema BOC_DB.BOC_RAW          to role BOC_ROLE;
grant all on schema BOC_DB.BOC_ANALYTICS    to role BOC_ROLE;
grant all on schema BOC_DB.BOC_ANALYTICS_CI to role BOC_ROLE;

grant all on all    tables in database BOC_DB to role BOC_ROLE;
grant all on future tables in database BOC_DB to role BOC_ROLE;
grant all on all    views  in database BOC_DB to role BOC_ROLE;
grant all on future views  in database BOC_DB to role BOC_ROLE;

-- ---------------------------------------------------------------------------
-- Sanity check — should return BOC_ROLE / BOC_WH / BOC_DB
-- ---------------------------------------------------------------------------
use role BOC_ROLE;
use warehouse BOC_WH;
use database BOC_DB;
select current_role(), current_warehouse(), current_database();
