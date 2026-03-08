#!/bin/bash
    
podman run -d \
    --name mindstate \
    -e POSTGRES_PASSWORD=secret \
    -p 5432:5432  \
    -v db:/var/lib/postgresql \
    -d localhost/mindstate-pg
