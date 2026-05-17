import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Sparkles, ArrowRight, Briefcase } from 'lucide-react';

export default function Occupation() {
  const [occupation, setOccupation] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (occupation) {
      localStorage.setItem('userOccupation', occupation);
      navigate('/onboarding/title');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="p-8">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Guidepost
          </h1>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Progress indicator */}
          <div className="flex items-center justify-center gap-2 mb-8">
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
          </div>

          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                <Briefcase className="w-8 h-8 text-indigo-600" />
              </div>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">What&apos;s your occupation?</h2>
              <p className="text-slate-600">Tell us about your professional field</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <Label htmlFor="occupation" className="text-slate-700">
                  Occupation
                </Label>
                <Input
                  id="occupation"
                  type="text"
                  value={occupation}
                  onChange={(e) => setOccupation(e.target.value)}
                  required
                  placeholder="e.g., Software Engineer, Marketing Manager"
                  className="mt-2 h-12 rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>

              <Button className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200">
                Continue
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
