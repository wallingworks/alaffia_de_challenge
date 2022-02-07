create table coins (
id text,
exchanges text,
task_run int
);

pragma journal_mode = WAL;
pragma synchronous = normal;
pragma temp_store = memory;
pragma mmap_size = 30000000000;
pragma read_uncommitted = true;