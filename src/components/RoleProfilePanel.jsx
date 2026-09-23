import { UserCog, ChevronDown, ChevronRight, Pencil, Plus, Trash2, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { LOCATION_KEYWORDS, parseKeywordList, formatKeywordList } from '../services/roleProfileService';

const EMPTY_FORM = {
  name: '',
  includeText: '',
  excludeText: '',
  searchDescription: false
};

function KeywordChips({ keywords, className }) {
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {keywords.map(keyword => (
        <span key={keyword} className={`px-2 py-0.5 text-xs rounded-full ${className}`}>
          {keyword}
        </span>
      ))}
    </div>
  );
}

export default function RoleProfilePanel({
  profiles,
  activeProfile,
  onSelectProfile,
  onSaveProfile,
  onDeleteProfile,
  onResetProfiles
}) {
  const [isOpen, setIsOpen] = useState(true);
  // null = not editing, 'new' = creating, otherwise the id being edited
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState([]);

  const closeForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setErrors([]);
  };

  const startEdit = () => {
    if (!activeProfile) return;
    setEditingId(activeProfile.id);
    setForm({
      name: activeProfile.name,
      includeText: formatKeywordList(activeProfile.includeKeywords),
      excludeText: formatKeywordList(activeProfile.excludeTitleKeywords),
      searchDescription: activeProfile.searchDescription === true
    });
    setErrors([]);
  };

  const startNew = () => {
    setEditingId('new');
    setForm({
      ...EMPTY_FORM,
      excludeText: formatKeywordList(activeProfile?.excludeTitleKeywords ?? [])
    });
    setErrors([]);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const name = form.name.trim();
    const includeKeywords = parseKeywordList(form.includeText);
    const excludeTitleKeywords = parseKeywordList(form.excludeText);

    const nextErrors = [];
    if (!name) {
      nextErrors.push('Role name is required.');
    } else if (profiles.some(p => p.id !== editingId && p.name.toLowerCase() === name.toLowerCase())) {
      nextErrors.push('A role with this name already exists.');
    }
    if (includeKeywords.length === 0) {
      nextErrors.push('Add at least one include keyword.');
    }
    if (nextErrors.length > 0) {
      setErrors(nextErrors);
      return;
    }

    onSaveProfile({
      id: editingId === 'new' ? null : editingId,
      name,
      includeKeywords,
      excludeTitleKeywords,
      searchDescription: form.searchDescription
    });
    closeForm();
  };

  const handleDelete = () => {
    if (!activeProfile || profiles.length <= 1) return;
    if (window.confirm(`Delete the "${activeProfile.name}" role?`)) {
      closeForm();
      onDeleteProfile(activeProfile.id);
    }
  };

  const handleReset = () => {
    if (window.confirm('Reset all roles to the defaults? Custom roles and edits will be lost.')) {
      closeForm();
      onResetProfiles();
    }
  };

  const handleSelect = (id) => {
    closeForm();
    onSelectProfile(id);
  };

  const inputClass =
    'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent';
  const buttonClass =
    'flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 rounded-md hover:bg-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <UserCog className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700">Role Profile</span>
          {activeProfile && (
            <span className="text-xs text-slate-500">{activeProfile.name}</span>
          )}
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="mt-3">
            <label htmlFor="role-profile-select" className="text-xs font-medium text-slate-500">
              Role
            </label>
            <select
              id="role-profile-select"
              value={activeProfile?.id ?? ''}
              onChange={(e) => handleSelect(e.target.value)}
              className={`${inputClass} mt-1 bg-white`}
            >
              {profiles.map(profile => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            <button type="button" onClick={startEdit} disabled={!activeProfile} className={buttonClass}>
              <Pencil className="w-3 h-3" />
              Edit
            </button>
            <button type="button" onClick={startNew} className={buttonClass}>
              <Plus className="w-3 h-3" />
              New role
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={!activeProfile || profiles.length <= 1}
              title={profiles.length <= 1 ? 'At least one role is required' : undefined}
              className={buttonClass}
            >
              <Trash2 className="w-3 h-3" />
              Delete
            </button>
            <button type="button" onClick={handleReset} className={buttonClass}>
              <RotateCcw className="w-3 h-3" />
              Reset defaults
            </button>
          </div>

          {editingId ? (
            <form onSubmit={handleSubmit} className="mt-4 space-y-3">
              <div>
                <label htmlFor="role-name" className="text-xs font-medium text-slate-500">
                  Name
                </label>
                <input
                  id="role-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Data Engineer"
                  className={`${inputClass} mt-1`}
                />
              </div>

              <div>
                <label htmlFor="role-include" className="text-xs font-medium text-slate-500">
                  Include keywords
                </label>
                <textarea
                  id="role-include"
                  rows={5}
                  value={form.includeText}
                  onChange={(e) => setForm({ ...form, includeText: e.target.value })}
                  placeholder="One per line or comma-separated"
                  className={`${inputClass} mt-1 font-mono text-xs`}
                />
              </div>

              <div>
                <label htmlFor="role-exclude" className="text-xs font-medium text-slate-500">
                  Exclude title words
                </label>
                <textarea
                  id="role-exclude"
                  rows={3}
                  value={form.excludeText}
                  onChange={(e) => setForm({ ...form, excludeText: e.target.value })}
                  placeholder="e.g. Senior, Staff, Manager"
                  className={`${inputClass} mt-1 font-mono text-xs`}
                />
              </div>

              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={form.searchDescription}
                  onChange={(e) => setForm({ ...form, searchDescription: e.target.checked })}
                  className="rounded border-slate-300 text-amber-500 focus:ring-amber-500"
                />
                Also match job description
              </label>

              <p className="text-xs text-slate-400">
                Whole-word, case-insensitive. Quote a keyword to keep a comma in it, e.g. "Software Engineer, Web".
              </p>

              {errors.length > 0 && (
                <ul className="text-xs text-red-600 space-y-0.5">
                  {errors.map(error => <li key={error}>{error}</li>)}
                </ul>
              )}

              <div className="flex gap-2">
                <button
                  type="submit"
                  className="px-3 py-1.5 text-xs font-medium text-white bg-amber-500 rounded-md hover:bg-amber-600 transition-colors"
                >
                  {editingId === 'new' ? 'Create role' : 'Save changes'}
                </button>
                <button
                  type="button"
                  onClick={closeForm}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 rounded-md hover:bg-slate-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            activeProfile && (
              <>
                <div className="mt-3">
                  <span className="text-xs font-medium text-slate-500">
                    Include Keywords ({activeProfile.includeKeywords.length})
                  </span>
                  <KeywordChips
                    keywords={activeProfile.includeKeywords}
                    className="bg-emerald-50 text-emerald-700"
                  />
                </div>

                {activeProfile.excludeTitleKeywords.length > 0 && (
                  <div className="mt-3">
                    <span className="text-xs font-medium text-slate-500">Exclude Title Keywords</span>
                    <KeywordChips
                      keywords={activeProfile.excludeTitleKeywords}
                      className="bg-red-50 text-red-700"
                    />
                  </div>
                )}

                <div className="mt-3">
                  <span className="text-xs font-medium text-slate-500">Location Keywords</span>
                  <KeywordChips keywords={LOCATION_KEYWORDS} className="bg-sky-50 text-sky-700" />
                </div>

                <p className="text-xs text-slate-400 mt-3">
                  Matching {activeProfile.searchDescription ? 'job title and description' : 'job title only'}.
                  Roles are saved in this browser.
                </p>
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}
