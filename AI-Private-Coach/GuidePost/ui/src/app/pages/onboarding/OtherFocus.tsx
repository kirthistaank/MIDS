import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Sparkles, ArrowRight, MessageSquare } from 'lucide-react';

export default function OtherFocus() {
  const [otherFocus, setOtherFocus] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('otherFocus', otherFocus);
    navigate('/onboarding/voice-recording');
  };

  const handleSkip = () => {
    localStorage.setItem('otherFocus', '');
    navigate('/onboarding/voice-recording');
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
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-slate-200" />
          </div>

          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
                <MessageSquare className="w-8 h-8 text-indigo-600" />
              </div>
            </div>

            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">Anything else?</h2>
              <p className="text-slate-600">Tell us about other areas you&apos;d like to focus on improving</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <Label htmlFor="otherFocus" className="text-slate-700">
                  Additional focus areas <span className="text-slate-400 font-normal">(optional)</span>
                </Label>
                <Textarea
                  id="otherFocus"
                  value={otherFocus}
                  onChange={(e) => setOtherFocus(e.target.value)}
                  placeholder="e.g., Time management, team leadership, public speaking..."
                  rows={6}
                  className="mt-2 rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500 resize-none"
                />
              </div>

              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSkip}
                  className="flex-1 h-12 rounded-xl border-slate-200 hover:border-indigo-200 hover:bg-indigo-50"
                >
                  Skip
                </Button>
                <Button
                  type="submit"
                  className="flex-1 h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
                >
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
