import { Component, OnInit } from '@angular/core';
import { Http } from '@angular/http';
import { Search } from '../search';

@Component({
  selector: 'app-search-form',
  templateUrl: './search-form.component.html',
  styleUrls: ['./search-form.component.css']
})
export class SearchFormComponent implements OnInit {

  constructor(
  	public http: Http
  ) { }

  ngOnInit() {
  }

  model = new Search('');
  result = [];
  resultType = '';

  submitted = false;

  onSubmit() { 
  	this.submitted = true;
  	this.http.get('/explorer-search?term=' + encodeURIComponent(this.model.term))
  	.subscribe((res: any) => {
  		this.result = res.json().result
  		this.resultType = res.json().resultType
  	},
  	(err: any) => {
  		alert('something went terribly wrong!')
  	});	
  }

  // TODO: Remove this when we're done
  get diagnostic() { return JSON.stringify(this.model); }
}
