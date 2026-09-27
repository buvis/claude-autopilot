#!/bin/bash
# List available PRD files from wip and backlog directories

echo "=== PRDs in Progress (wip) ==="
if [ -d "docs/dev/project-management/prds/wip" ] && [ "$(ls -A docs/dev/project-management/prds/wip 2>/dev/null)" ]; then
    ls -1 docs/dev/project-management/prds/wip/
else
    echo "(none)"
fi

echo ""
echo "=== PRDs in Backlog ==="
if [ -d "docs/dev/project-management/prds/backlog" ] && [ "$(ls -A docs/dev/project-management/prds/backlog 2>/dev/null)" ]; then
    ls -1 docs/dev/project-management/prds/backlog/
else
    echo "(none)"
fi

echo ""
echo "=== Completed PRDs (done) ==="
if [ -d "docs/dev/project-management/prds/done" ] && [ "$(ls -A docs/dev/project-management/prds/done 2>/dev/null)" ]; then
    ls -1 docs/dev/project-management/prds/done/
else
    echo "(none)"
fi
