import {Component,type ReactNode} from 'react';

// React render failures happen after the async loader completes. Keep an
// actionable message mounted instead of allowing React to clear the root.
export default class WorkspaceBoundary extends Component<{children:ReactNode;retry:()=>void},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true}}
 render(){
  if(this.state.failed)return <div className="workspace-connecting workspace-startup"><main><p className="eyebrow">STOCK &amp; PLANNING</p><h1>Workspace could not be displayed</h1><p role="alert">A saved view could not be rendered. Your workbook and saved reports have not been changed.</p><button className="primary" onClick={this.props.retry}>Retry loading</button></main></div>;
  return this.props.children;
 }
}
