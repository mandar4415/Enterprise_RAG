import React from 'react';
import DashboardLayout from '../components/DashboardLayout';
import ChatInterface from '../components/ChatInterface';

export default function Dashboard() {
  return (
    <DashboardLayout>
      <ChatInterface />
    </DashboardLayout>
  );
}
