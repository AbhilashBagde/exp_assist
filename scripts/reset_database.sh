#!/bin/bash
# Script to clear all test data from ExportAssist database

echo "🗑️  Clearing ExportAssist database..."

mongosh exportassist --quiet --eval "
  db.users.deleteMany({});
  db.company_profiles.deleteMany({});
  db.shipments.deleteMany({});
  print('✅ All data cleared successfully!');
  print('');
  print('You can now signup with a fresh account.');
"

echo ""
echo "Database reset complete!"
echo ""
echo "Next steps:"
echo "1. Go to http://localhost:3000"
echo "2. Click 'Sign Up'"
echo "3. Create a new account with any email"
echo ""
