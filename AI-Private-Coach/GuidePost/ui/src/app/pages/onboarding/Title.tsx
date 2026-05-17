import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../components/ui/button';
import { Label } from '../../components/ui/label';
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group';
import { Sparkles, ArrowRight, Award } from 'lucide-react';

const SENIORITY_LEVELS = [
  'Individual Contributor',
  'People Manager',
  'Director/VP',
  'Executive',
];

export default function Title() {
  const [seniorityLevel, setSeniorityLevel] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (seniorityLevel) {
      localStorage.setItem('userSeniorityLevel', seniorityLevel);
      navigate('/onboarding/rank-skills');
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
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
          </div>

          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                <Award className="w-8 h-8 text-indigo-600" />
              </div>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">What&apos;s your seniority level?</h2>
              <p className="text-slate-600">Select the option that best describes your role</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <RadioGroup value={seniorityLevel} onValueChange={setSeniorityLevel}>
                <div className="space-y-3">
                  {SENIORITY_LEVELS.map((level) => (
                    <div
                      key={level}
                      className={`relative flex items-center space-x-4 p-5 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                        seniorityLevel === level
                          ? 'border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-md shadow-indigo-100'
                          : 'border-slate-200 hover:border-indigo-200 bg-white hover:shadow-sm'
                      }`}
                      onClick={() => setSeniorityLevel(level)}
                    >
                      <RadioGroupItem value={level} id={level} className="border-slate-300" />
                      <Label htmlFor={level} className="flex-1 cursor-pointer text-slate-900 font-medium">
                        {level}
                      </Label>
                      {seniorityLevel === level && <div className="w-2 h-2 rounded-full bg-indigo-600" />}
                    </div>
                  ))}
                </div>
              </RadioGroup>

              <Button
                type="submit"
                className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200 disabled:opacity-50"
                disabled={!seniorityLevel}
              >
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