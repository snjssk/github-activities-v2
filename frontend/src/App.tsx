import { useEffect, useState } from 'react';
import { api, User } from './api/client';
import Dashboard from './components/Dashboard';

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getUsers()
      .then((data) => {
        setUsers(data);
        if (data.length > 0) {
          setSelectedUser(data[0].username);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-500">Error: {error}</div>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-800 mb-4">
            GitHub Activities Dashboard
          </h1>
          <p className="text-gray-500">
            No users registered. Run the CLI to add users:
          </p>
          <code className="block mt-2 bg-gray-100 p-2 rounded">
            python -m github_activities.cli add-user USERNAME --backfill-from 2024-01-01
          </code>
        </div>
      </div>
    );
  }

  return (
    <Dashboard
      users={users}
      selectedUser={selectedUser}
      onUserChange={setSelectedUser}
    />
  );
}

export default App;
