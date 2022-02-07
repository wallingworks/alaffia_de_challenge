# Flask Coin Transformer

Flask based docker hosted ETL for coins problem.

Uses postres for persistent storage and redis for caching.

## Run

docker-compose up --build

## Results

Results are returned for each request.  Additionally information is saved to database and can be viewed directly in the database with your favorite postgres client while
the container is running.  Credentials are available in .env

## Notes/Bugs

Timings reported by app sometimes exceed 400ms, but coin-spewer does not report failure in those cases.
